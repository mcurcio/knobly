// refused: exceeds 400 states
// The choice is decided by the ninth token before the ';', so the lookahead machine must remember the last nine
// tokens: 2^9 states and more, over the limit.
grammar StateLimit;

start : (A | B)* A (A | B) (A | B) (A | B) (A | B) (A | B) (A | B) (A | B) (A | B) END EOF
      | (A | B)* B (A | B) (A | B) (A | B) (A | B) (A | B) (A | B) (A | B) (A | B) END EOF ;
A   : 'a' ;
B   : 'b' ;
END : ';' ;
