// PLANTED (must be caught by the overlap check): a WORD that may start with '@', so '@set' is both a WORD and an
// AT_WORD.
// knobly grammar, ported from knobly.ebnf (draft 2 + rasl-trv: '*' and '?' in words;
// round 11: variables; milestone 4: ';' ends every statement, the text-only rules as entry rules;
// milestone 5: raw single quotes, the '~' slice separator, subscripts on variables, '@' statements).
// Whitespace is explicit: every token is on the default channel, nothing is skipped.
// A line break is whitespace (owner, 2026-10-29, Q1: "';' is required and a line break is plain whitespace (nginx);
// directive names cannot start with a digit or '-'").
// Milestone 5 (owner, 2026-10-29, bead kno-umh.14): single quotes are raw strings (TOML literal strings: no escapes);
// a slice's separator is outside the word alphabet, so ':' is a word character everywhere ('..', the proposed
// spelling, cannot lex next to number-like words, so it is '~': spec 3.1); a variable may be subscripted; a
// statement written '@name' is a language or extension statement, never a directive.
grammar Knobly;

document      : BOM? statements EOF ;
statements    : filler* (directive filler*)* ;
filler        : SPACE | COMMENT | NEWLINE | ';' ;
directive     : header (';' | block) ;
header        : (WORD | AT_WORD) rest ;              // an AT_WORD heads a language or extension statement
rest          : (gap value)* gap? ;
gap           : (SPACE | NEWLINE | COMMENT NEWLINE)+ ;   // a comment runs to the end of its line
block         : '{' statements '}' ;
value         : WORD | AT_WORD | INTEGER | DIGIT_WORD | STRING | VARIABLE | slicedWord | list ;
slicedWord    : sliceName '[' bounds ']' ;
sliceName     : WORD | AT_WORD | VARIABLE ;           // a word, or a variable holding one word
bounds        : bound '~' bound? | '~' bound | bound ;
bound         : INTEGER | VARIABLE ;
list          : '[' gap? items? ']' ;
items         : value gap? (',' gap? value gap?)* (',' gap?)? ;

// Entry rules (spec 2.8): a text a program hands to an edit or an override, parsed on its own. A binding parses
// such a text with the rule named here, never by splicing it into a probe document.
statementsText : statements EOF ;                                 // a statement's replace, insert or add statements: no BOM
valuesText    : gap? (value (gap value)* gap?)? EOF ;             // a line's values: set, a value's replace, an override
valueText     : gap? value gap? EOF ;                             // a value's set: exactly one value
itemsText     : gap? (value gap? (',' gap? value gap?)*)? EOF ;   // a list item's replace: items, no trailing ','
boundText     : bound EOF ;                                       // a slice or index bound's set or replace
sliceNameText : sliceName EOF ;                                   // a slice or index name's set or replace
nameText      : WORD EOF ;                                        // a directive's rename, an extension's name

BOM        : '﻿' ;
SPACE      : [ \t]+ ;
NEWLINE    : '\n' | '\r\n' ;
COMMENT    : '#' CHAR* ;
VARIABLE   : '$' [A-Za-z0-9_]+ ;   // $ + letters, digits and _ (nginx's name rule, round 11 L1)
WORD       : [A-Za-z_./*?@] NAME_CHAR* ;                   // the only word a directive name can be
AT_WORD    : '@' NAME_CHAR* ;                             // '@set', '@include': a statement's keyword; also a value
INTEGER    : '-'? ('0' | [1-9] [0-9]*) ;                  // IntegerText: the only literal slice or index bound
DIGIT_WORD : '-'                                          // every other word that starts with a digit or '-'
           | '-' NOT_DIGIT NAME_CHAR*
           | '-'? '0' NAME_CHAR+
           | '-'? [1-9] [0-9]* NOT_DIGIT NAME_CHAR* ;
STRING     : '"' (~["\\\u0000-\u0008\n-\u001F\u007F\uD800-\uDFFF] | ESCAPE)* '"'
           | '\'' ~['\u0000-\u0008\n-\u001F\u007F\uD800-\uDFFF]* '\'' ;   // single quotes: raw, no escapes
LBRACE : '{' ; RBRACE : '}' ; LBRACK : '[' ; RBRACK : ']' ; SEMI : ';' ; COMMA : ',' ; TILDE : '~' ;
// error tokens: never used by the syntax
UNTERMINATED_STRING : '"' (~["\\\u0000-\u0008\n-\u001F\u007F\uD800-\uDFFF] | '\\' CHAR)* '\\'?
                    | '\'' ~['\u0000-\u0008\n-\u001F\u007F\uD800-\uDFFF]* ;
BAD_ESCAPE : '"' (~["\\\u0000-\u0008\n-\u001F\u007F\uD800-\uDFFF] | '\\' CHAR)* '\\' NOT_ESCAPE
             (~["\\\u0000-\u0008\n-\u001F\u007F\uD800-\uDFFF] | '\\' CHAR)* '"' ;   // a closed double-quoted string with a bad escape
LONE_DOLLAR : '$' ;   // a '$' with no name after it
BAD_CHAR : ~[\t\n "#$',./0-9;@A-Z_a-z{}*?[\]\-~﻿] ;   // = AnyChar - TokenStart: disjoint from every other kind
fragment CHAR : [\t -~\u0080-퟿-\u{10FFFF}] ;
fragment ESCAPE : '\\' ["'\\ntr] ;                                          // EscapeText: the six escapes (double quotes only)
fragment NOT_ESCAPE : [\t -!#-&(-[\]-mo-qsu-~\u0080-퟿-\u{10FFFF}] ;   // CHAR - ["'\\ntr]
fragment NAME_CHAR : [A-Za-z0-9_./@#+:*?-] ;                               // every word's characters after its first
fragment NOT_DIGIT : [A-Za-z_./@#+:*?-] ;                                  // NAME_CHAR - [0-9]
