"""Lightweight AST-based Python execution sandbox for Code-First Agents.

This module parses Python code into an Abstract Syntax Tree (AST), validates
every node against strict security policies, and executes permitted operations
in an isolated in-memory environment without invoking arbitrary exec/eval.
"""

import ast
import operator
from collections.abc import Callable
from typing import Any, ClassVar


class SecurityError(Exception):
    """Raised when code violates sandbox security constraints."""


class FlowControlSignal(Exception):
    """Base exception for flow control in the AST interpreter."""


class BreakSignal(FlowControlSignal):
    """Signaled when a break statement is encountered."""


class ContinueSignal(FlowControlSignal):
    """Signaled when a continue statement is encountered."""


class ASTSandbox:
    """Evaluates Python AST nodes in a safe, memory-bounded environment."""

    BINARY_OPERATORS: ClassVar[dict[type[ast.operator], Callable[[Any, Any], Any]]] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }

    COMPARE_OPERATORS: ClassVar[dict[type[ast.cmpop], Callable[[Any, Any], Any]]] = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
        ast.In: lambda a, b: a in b,
        ast.NotIn: lambda a, b: a not in b,
        ast.Is: operator.is_,
        ast.IsNot: operator.is_not,
    }

    UNARY_OPERATORS: ClassVar[dict[type[ast.unaryop], Callable[[Any], Any]]] = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
        ast.Not: operator.not_,
    }

    SAFE_BUILTINS: ClassVar[dict[str, Any]] = {
        "print": print,
        "len": len,
        "range": range,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "list": list,
        "dict": dict,
        "set": set,
        "tuple": tuple,
        "sum": sum,
        "min": min,
        "max": max,
        "round": round,
        "enumerate": enumerate,
        "zip": zip,
    }

    def __init__(
        self,
        tools: dict[str, Callable[..., Any]] | None = None,
        max_loop_iterations: int = 1000,
    ) -> None:
        """Initialize the sandbox with registered tools and loop bounds.

        Args:
            tools: Dictionary of callable tools made accessible to the agent.
            max_loop_iterations: Maximum loop turns allowed to avoid CPU starvation.
        """
        self.max_loop_iterations = max_loop_iterations
        self.registered_tools = tools or {}
        self.environment: dict[str, Any] = {}
        self.final_answer_value: Any = None
        self._reset_environment()

    def _reset_environment(self) -> None:
        """Reset execution environment and inject tools and safe builtins."""
        self.environment = dict(self.SAFE_BUILTINS)
        self.environment.update(self.registered_tools)
        self.environment["final_answer"] = self._record_final_answer
        self.final_answer_value = None

    def _record_final_answer(self, value: Any) -> Any:
        """Record the final answer submitted by the agent."""
        self.final_answer_value = value
        return value

    def execute(self, code: str) -> dict[str, Any]:
        """Parse and safely execute Python code string.

        Args:
            code: Python source code snippet emitted by the model.

        Returns:
            Dictionary containing final_answer and snapshot of environment variables.

        Raises:
            SecurityError: If forbidden syntax, imports, or dunder attributes are detected.
        """
        self._reset_environment()
        try:
            tree = ast.parse(code)
        except SyntaxError as err:
            raise ValueError(f"Syntax error in agent code: {err}") from err

        for statement in tree.body:
            self._execute_statement(statement)

        return {
            "final_answer": self.final_answer_value,
            "variables": {
                k: v
                for k, v in self.environment.items()
                if k not in self.SAFE_BUILTINS and k not in self.registered_tools and k != "final_answer"
            },
        }

    def _execute_statement(self, stmt: ast.stmt) -> None:
        """Execute a single AST statement node."""
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            raise SecurityError(
                f"Security violation: imports ({ast.unparse(stmt)}) are strictly forbidden in AST sandbox."
            )

        if isinstance(stmt, (ast.Delete, ast.Global, ast.Nonlocal, ast.Try, ast.With)):
            raise SecurityError(f"Security violation: statement '{type(stmt).__name__}' is disabled.")

        if isinstance(stmt, ast.Assign):
            val = self._eval_expression(stmt.value)
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    self._validate_identifier(target.id)
                    self.environment[target.id] = val
                elif isinstance(target, ast.Subscript):
                    container = self._eval_expression(target.value)
                    index = self._eval_expression(target.slice)
                    container[index] = val
                else:
                    raise SecurityError(f"Complex assignment target '{type(target).__name__}' not permitted.")
            return

        if isinstance(stmt, ast.AugAssign):
            val = self._eval_expression(stmt.value)
            if isinstance(stmt.target, ast.Name):
                self._validate_identifier(stmt.target.id)
                current = self.environment.get(stmt.target.id, 0)
                op_type = type(stmt.op)
                if op_type not in self.BINARY_OPERATORS:
                    raise SecurityError(f"Unsupported augmented operator {op_type.__name__}")
                self.environment[stmt.target.id] = self.BINARY_OPERATORS[op_type](current, val)
            else:
                raise SecurityError("Augmented assignment only permitted on variable names.")
            return

        if isinstance(stmt, ast.Expr):
            self._eval_expression(stmt.value)
            return

        if isinstance(stmt, ast.If):
            test_val = self._eval_expression(stmt.test)
            branch = stmt.body if test_val else stmt.orelse
            for inner_stmt in branch:
                self._execute_statement(inner_stmt)
            return

        if isinstance(stmt, ast.For):
            iterable = self._eval_expression(stmt.iter)
            if not isinstance(stmt.target, ast.Name):
                raise SecurityError("For loops only support simple variable targets.")

            var_name = stmt.target.id
            self._validate_identifier(var_name)

            iterations = 0
            for item in iterable:
                iterations += 1
                if iterations > self.max_loop_iterations:
                    raise SecurityError(f"Loop iteration limit ({self.max_loop_iterations}) exceeded.")
                self.environment[var_name] = item
                try:
                    for inner_stmt in stmt.body:
                        self._execute_statement(inner_stmt)
                except BreakSignal:
                    break
                except ContinueSignal:
                    continue
            return

        if isinstance(stmt, ast.Break):
            raise BreakSignal()

        if isinstance(stmt, ast.Continue):
            raise ContinueSignal()

        if isinstance(stmt, ast.Pass):
            return

        raise SecurityError(f"Unsupported AST statement type: {type(stmt).__name__}")

    def _eval_expression(self, node: ast.expr) -> Any:
        """Recursively evaluate an AST expression node."""
        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Name):
            self._validate_identifier(node.id)
            if node.id not in self.environment:
                raise NameError(f"Variable '{node.id}' is not defined in sandbox.")
            return self.environment[node.id]

        if isinstance(node, ast.UnaryOp):
            op_func = self.UNARY_OPERATORS.get(type(node.op))
            if not op_func:
                raise SecurityError(f"Unsupported unary operator: {type(node.op).__name__}")
            return op_func(self._eval_expression(node.operand))

        if isinstance(node, ast.BinOp):
            op_func = self.BINARY_OPERATORS.get(type(node.op))
            if not op_func:
                raise SecurityError(f"Unsupported binary operator: {type(node.op).__name__}")
            left = self._eval_expression(node.left)
            right = self._eval_expression(node.right)
            return op_func(left, right)

        if isinstance(node, ast.Compare):
            left = self._eval_expression(node.left)
            for op, comparator in zip(node.ops, node.comparators, strict=False):
                op_func = self.COMPARE_OPERATORS.get(type(op))
                if not op_func:
                    raise SecurityError(f"Unsupported comparison operator: {type(op).__name__}")
                right = self._eval_expression(comparator)
                if not op_func(left, right):
                    return False
                left = right
            return True

        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                res = True
                for val_node in node.values:
                    res = self._eval_expression(val_node)
                    if not res:
                        return res
                return res
            if isinstance(node.op, ast.Or):
                res = False
                for val_node in node.values:
                    res = self._eval_expression(val_node)
                    if res:
                        return res
                return res
            raise SecurityError(f"Unsupported boolean operator {type(node.op).__name__}")

        if isinstance(node, ast.List):
            return [self._eval_expression(elt) for elt in node.elts]

        if isinstance(node, ast.Tuple):
            return tuple(self._eval_expression(elt) for elt in node.elts)

        if isinstance(node, ast.Dict):
            return {
                self._eval_expression(k): self._eval_expression(v)
                for k, v in zip(node.keys, node.values, strict=False)
                if k is not None
            }

        if isinstance(node, ast.Attribute):
            self._validate_identifier(node.attr)
            obj = self._eval_expression(node.value)
            return getattr(obj, node.attr)

        if isinstance(node, ast.Subscript):
            target = self._eval_expression(node.value)
            slice_val = self._eval_expression(node.slice)
            return target[slice_val]

        if isinstance(node, ast.Call):
            func = self._eval_expression(node.func)
            args = [self._eval_expression(arg) for arg in node.args]
            kwargs = {kw.arg: self._eval_expression(kw.value) for kw in node.keywords if kw.arg is not None}
            if not callable(func):
                raise TypeError(f"Attempted to call non-callable object {func}")
            return func(*args, **kwargs)

        if isinstance(node, ast.JoinedStr):
            # Formatted f-string support
            parts = []
            for part in node.values:
                if isinstance(part, ast.FormattedValue):
                    parts.append(str(self._eval_expression(part.value)))
                elif isinstance(part, ast.Constant):
                    parts.append(str(part.value))
                else:
                    raise SecurityError(f"Unsupported f-string segment {type(part).__name__}")
            return "".join(parts)

        raise SecurityError(f"Expression type '{type(node).__name__}' is disabled in AST sandbox.")

    @staticmethod
    def _validate_identifier(name: str) -> None:
        """Ensure variable or attribute name does not attempt dunder introspection."""
        if name.startswith("__"):
            raise SecurityError(
                f"Security violation: access to private/dunder attribute '{name}' is forbidden."
            )
