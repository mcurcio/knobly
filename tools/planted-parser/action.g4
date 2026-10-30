// refused: an action
// An action embeds target-language code in the grammar; the generated parser is grammar-shaped only.
grammar Action;

start : WORD {count++;} EOF ;
WORD  : [a-z]+ ;
