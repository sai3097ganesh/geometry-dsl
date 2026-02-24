from dataclasses import dataclass
import copy
from typing import List

from dsl_ast import Call, Expr, Number, Vec2, Vec3
from dsl_lexer import Lexer, Token


class ParserError(Exception):
    pass


@dataclass
class Parser:
    tokens: List[Token]
    i: int = 0

    @staticmethod
    def from_source(src: str) -> "Parser":
        return Parser(Lexer(src).tokenize())

    def _peek(self) -> Token:
        return self.tokens[self.i]

    def _peek_next(self) -> Token:
        if self.i + 1 < len(self.tokens):
            return self.tokens[self.i + 1]
        return self.tokens[-1]

    def _advance(self) -> Token:
        tok = self._peek()
        self.i += 1
        return tok

    def _expect(self, kind: str) -> Token:
        tok = self._peek()
        if tok.kind != kind:
            raise ParserError(f"Expected {kind} at {tok.line}:{tok.col}, got {tok.kind}")
        return self._advance()

    def parse_expr(self, bindings: dict[str, Expr] | None = None) -> Expr:
        tok = self._peek()
        if tok.kind == "NUMBER":
            self._advance()
            return Number(tok.value or 0.0)
        if tok.kind == "IDENT":
            name = self._advance().lexeme
            if self._peek().kind == "LPAREN":
                self._expect("LPAREN")
                args: List[Expr] = []
                if self._peek().kind != "RPAREN":
                    while True:
                        args.append(self.parse_expr(bindings))
                        if self._peek().kind == "COMMA":
                            self._advance()
                            continue
                        break
                self._expect("RPAREN")
                if name == "vec3":
                    if len(args) != 3:
                        raise ParserError("vec3 expects 3 arguments")
                    return Vec3(args[0], args[1], args[2])
                if name == "vec2":
                    if len(args) != 2:
                        raise ParserError("vec2 expects 2 arguments")
                    return Vec2(args[0], args[1])
                return Call(name, args)

            if bindings is not None and name in bindings:
                return copy.deepcopy(bindings[name])
            raise ParserError(f"Unexpected identifier {name} at {tok.line}:{tok.col}")
        raise ParserError(f"Unexpected token {tok.kind} at {tok.line}:{tok.col}")

    def _parse_return_exprs(self, bindings: dict[str, Expr]) -> List[Expr]:
        self._expect("RETURN")
        exprs: List[Expr] = []
        while True:
            exprs.append(self.parse_expr(bindings))
            if self._peek().kind == "COMMA":
                self._advance()
                continue
            break
        return exprs

    def parse(self) -> Expr:
        bindings: dict[str, Expr] = {}
        saw_statement = False

        while self._peek().kind != "EOF":
            tok = self._peek()

            if tok.kind == "IDENT" and self._peek_next().kind == "EQUAL":
                saw_statement = True
                name = self._advance().lexeme
                self._expect("EQUAL")
                bindings[name] = self.parse_expr(bindings)
                continue

            if tok.kind == "RETURN":
                saw_statement = True
                exprs = self._parse_return_exprs(bindings)
                if self._peek().kind != "EOF":
                    extra = self._peek()
                    raise ParserError(
                        f"Unexpected token {extra.kind} at {extra.line}:{extra.col}"
                    )
                if len(exprs) == 1:
                    return exprs[0]
                return Call("union", exprs)

            if not saw_statement:
                expr = self.parse_expr()
                if self._peek().kind != "EOF":
                    extra = self._peek()
                    raise ParserError(
                        f"Unexpected token {extra.kind} at {extra.line}:{extra.col}"
                    )
                return expr

            raise ParserError(f"Expected assignment or return at {tok.line}:{tok.col}")

        raise ParserError("Expected expression or return statement")
