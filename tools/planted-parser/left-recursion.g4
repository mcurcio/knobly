// refused: left recursion
// A rule that reaches itself before consuming a token makes recursive descent loop forever.
grammar LeftRecursion;

start : sum EOF ;
sum   : sum PLUS WORD | WORD ;
WORD  : [a-z]+ ;
PLUS  : '+' ;
