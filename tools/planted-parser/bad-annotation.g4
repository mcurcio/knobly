// refused: names no rule
// A tree annotation must end the line where a parser rule starts; this one sits on the rule's second line.
grammar BadAnnotation;

start : WORD
        EOF ;   // cst: document
WORD  : [a-z]+ ;
