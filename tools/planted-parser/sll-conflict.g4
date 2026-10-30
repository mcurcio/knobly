// refused: an SLL conflict
// Two alternatives with the same continuation: no amount of lookahead tells `one` from `two` (an ambiguity).
grammar SllConflict;

start : (one | two) EOF ;
one   : WORD ;
two   : WORD ;
WORD  : [a-z]+ ;
