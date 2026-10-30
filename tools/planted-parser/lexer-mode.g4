// refused: a lexer command
// A lexer command (-> skip, -> channel) drops or hides text; knobly's tree is lossless, every token is kept.
grammar LexerMode;

start : WORD+ EOF ;
WORD  : [a-z]+ ;
SPACE : ' '+ -> skip ;
