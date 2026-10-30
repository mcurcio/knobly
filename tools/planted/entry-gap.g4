// PLANTED (must be caught): an entry rule whose gaps can split two ways (gap gap). Proves the entry rules are checked
// on their own, not only the document rule.
// knobly grammar, ported from knobly.ebnf (draft 2 + rasl-trv: '*' and '?' in words;
// round 11: variables; milestone 4: ';' ends every statement, the text-only rules as entry rules).
// Whitespace is explicit: every token is on the default channel, nothing is skipped.
// A line break is whitespace (owner, 2026-10-29, Q1: "';' is required and a line break is plain whitespace (nginx);
// directive names cannot start with a digit or '-'").
grammar Knobly;

document      : BOM? statements EOF ;
statements    : filler* (directive filler*)* ;
filler        : SPACE | COMMENT | NEWLINE | ';' ;
directive     : header (';' | block) ;
header        : WORD rest ;
rest          : (gap value)* gap? ;
gap           : (SPACE | NEWLINE | COMMENT NEWLINE)+ ;   // a comment runs to the end of its line
block         : '{' statements '}' ;
value         : WORD | INTEGER | DIGIT_WORD | STRING | VARIABLE | slicedWord | list ;
slicedWord    : WORD '[' bounds ']' ;
bounds        : bound ':' bound? | ':' bound | bound ;
bound         : INTEGER | VARIABLE ;
list          : '[' gap? items? ']' ;
items         : value gap? (',' gap? value gap?)* (',' gap?)? ;

// Entry rules (spec 2.8): a text a program hands to an edit or an override, parsed on its own. A binding parses
// such a text with the rule named here, never by splicing it into a probe document.
valuesText    : gap? (value | gap)* EOF ;
itemsText     : gap? (value gap? (',' gap? value gap?)*)? EOF ;   // a list item's replace: items, no trailing ','
boundText     : bound EOF ;                                       // a slice or index bound's replace
nameText      : WORD EOF ;                                        // a directive's rename

BOM        : '﻿' ;
SPACE      : [ \t]+ ;
NEWLINE    : '\n' | '\r\n' ;
COMMENT    : '#' CHAR* ;
VARIABLE   : '$' [A-Za-z0-9_]+ ;   // $ + letters, digits and _ (nginx's name rule, round 11 L1)
WORD       : [A-Za-z_./@*?] [A-Za-z0-9_./@#+:*?-]* ;   // the only word a directive name or a slice's name can be
INTEGER    : '-'? ('0' | [1-9] [0-9]*) ;                  // IntegerText: the only literal slice or index bound
DIGIT_WORD : '-'                                          // every other word that starts with a digit or '-'
           | '-' NOT_DIGIT NUMBER_CHAR*
           | '-'? '0' NUMBER_CHAR+
           | '-'? [1-9] [0-9]* NOT_DIGIT NUMBER_CHAR* ;
STRING     : '"' (~["\\\u0000-\u0008\n-\u001F\u007F\uD800-\uDFFF] | ESCAPE)* '"'
           | '\'' (~['\\\u0000-\u0008\n-\u001F\u007F\uD800-\uDFFF] | ESCAPE)* '\'' ;
LBRACE : '{' ; RBRACE : '}' ; LBRACK : '[' ; RBRACK : ']' ; SEMI : ';' ; COMMA : ',' ; COLON : ':' ;
// error tokens: never used by the syntax
UNTERMINATED_STRING : '"' (~["\\\u0000-\u0008\n-\u001F\u007F\uD800-\uDFFF] | '\\' CHAR)* '\\'?
                    | '\'' (~['\\\u0000-\u0008\n-\u001F\u007F\uD800-\uDFFF] | '\\' CHAR)* '\\'? ;
BAD_ESCAPE : '"' (~["\\\u0000-\u0008\n-\u001F\u007F\uD800-\uDFFF] | '\\' CHAR)* '\\' NOT_ESCAPE
             (~["\\\u0000-\u0008\n-\u001F\u007F\uD800-\uDFFF] | '\\' CHAR)* '"'
           | '\'' (~['\\\u0000-\u0008\n-\u001F\u007F\uD800-\uDFFF] | '\\' CHAR)* '\\' NOT_ESCAPE
             (~['\\\u0000-\u0008\n-\u001F\u007F\uD800-\uDFFF] | '\\' CHAR)* '\'' ;   // a closed string with a bad escape
LONE_DOLLAR : '$' ;   // a '$' with no name after it
BAD_CHAR : ~[\t\n "#$',./0-9:;@A-Z_a-z{}*?[\]\-﻿] ;   // = AnyChar - TokenStart: disjoint from every other kind
fragment CHAR : [\t -~\u0080-퟿-\u{10FFFF}] ;
fragment ESCAPE : '\\' ["'\\ntr] ;                                          // EscapeText: the six escapes
fragment NOT_ESCAPE : [\t -!#-&(-[\]-mo-qsu-~\u0080-퟿-\u{10FFFF}] ;   // CHAR - ["'\\ntr]
fragment NUMBER_CHAR : [A-Za-z0-9_./@#+*?-] ;
fragment NOT_DIGIT : [A-Za-z_./@#+*?-] ;                                   // NUMBER_CHAR - [0-9]
