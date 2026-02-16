from dataclasses import dataclass
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

    def _advance(self) -> Token:
        tok = self._peek()
        self.i += 1
        return tok

    def _expect(self, kind: str) -> Token:
        tok = self._peek()
        if tok.kind != kind:
            raise ParserError(f"Expected {kind} at {tok.line}:{tok.col}, got {tok.kind}")
        return self._advance()

    def parse_expr(self) -> Expr:
        tok = self._peek()
        if tok.kind == "NUMBER":
            self._advance()
            return Number(tok.value or 0.0)
        if tok.kind == "IDENT":
            name = self._advance().lexeme
            self._expect("LPAREN")
            args: List[Expr] = []
            if self._peek().kind != "RPAREN":
                while True:
                    args.append(self.parse_expr())
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
        raise ParserError(f"Unexpected token {tok.kind} at {tok.line}:{tok.col}")

    def parse(self) -> Expr:
        expr = self.parse_expr()
        if self._peek().kind != "EOF":
            tok = self._peek()
            raise ParserError(f"Unexpected token {tok.kind} at {tok.line}:{tok.col}")
        return expr
