from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Token:
    kind: str
    lexeme: str
    value: Optional[float]
    line: int
    col: int


class LexerError(Exception):
    pass


class Lexer:
    def __init__(self, src: str) -> None:
        self.src = src
        self.i = 0
        self.line = 1
        self.col = 1

    def _peek(self) -> str:
        return self.src[self.i] if self.i < len(self.src) else ""

    def _advance(self) -> str:
        ch = self._peek()
        self.i += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def _skip_whitespace_and_comments(self) -> None:
        while True:
            ch = self._peek()
            if not ch:
                break
            if ch in " \t\r\n":
                self._advance()
                continue
            if ch == "#":
                while self._peek() and self._peek() != "\n":
                    self._advance()
                continue
            break

    def _number(self) -> Token:
        start_i = self.i
        start_col = self.col
        saw_dot = False
        while True:
            ch = self._peek()
            if ch.isdigit():
                self._advance()
            elif ch == "." and not saw_dot:
                saw_dot = True
                self._advance()
            else:
                break
        lex = self.src[start_i:self.i]
        try:
            val = float(lex)
        except ValueError as exc:
            raise LexerError(f"Invalid number {lex} at {self.line}:{start_col}") from exc
        return Token("NUMBER", lex, val, self.line, start_col)

    def _ident(self) -> Token:
        start_i = self.i
        start_col = self.col
        while True:
            ch = self._peek()
            if ch.isalnum() or ch == "_":
                self._advance()
            else:
                break
        lex = self.src[start_i:self.i]
        return Token("IDENT", lex, None, self.line, start_col)

    def tokenize(self) -> List[Token]:
        tokens: List[Token] = []
        while True:
            self._skip_whitespace_and_comments()
            ch = self._peek()
            if not ch:
                tokens.append(Token("EOF", "", None, self.line, self.col))
                return tokens
            if ch.isdigit() or (ch == "." and self.i + 1 < len(self.src) and self.src[self.i + 1].isdigit()):
                tokens.append(self._number())
                continue
            if ch.isalpha() or ch == "_":
                tokens.append(self._ident())
                continue
            if ch == "(":
                self._advance()
                tokens.append(Token("LPAREN", "(", None, self.line, self.col - 1))
                continue
            if ch == ")":
                self._advance()
                tokens.append(Token("RPAREN", ")", None, self.line, self.col - 1))
                continue
            if ch == ",":
                self._advance()
                tokens.append(Token("COMMA", ",", None, self.line, self.col - 1))
                continue
            raise LexerError(f"Unexpected character {ch} at {self.line}:{self.col}")
