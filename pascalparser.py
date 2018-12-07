import re
import sys

# all possible token types. order determines priority.
token_types = [
    (r'{.*}', 'comment'),
    (r'program|var|integer|real|boolean|procedure|begin|end|if|then|else|while|do|not', 'reserved keyword'),

    (r':=', 'attribution'),
    (r'=|<|>|<=|>=|<>', 'comparison'),
    (r';|\.|:|\(|\)|,', 'delimiter'),

    (r'\+|-|or', 'additive operator'),
    (r'\*|/|and', 'multiplicative operator'),

    (r'[0-9]+', 'integer'),
    (r'[0-9]+\.[0-9]*', 'real'),
    (r'[a-z]+[a-z0-9_]*', 'identifier'),
    ]

# concatenate all of the above into a giant generic match regex
regex_str = ''
for regex_tuple in token_types:
    regex_str += '|({})'.format(regex_tuple[0])
regex_str = regex_str[1:] # remove initial "|"
generic_regex = re.compile(regex_str)

# application entry point
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python3 pascalparser.py <input file>')
        quit()

    # tokens in file:
    tokens = []

    with open(sys.argv[1], 'r') as file:
        for line_num, line in enumerate(file.readlines()):
            # regex matches for this line:
            matches = []

            # look for all matches in this line
            iterator = re.finditer(generic_regex, line.lower())

            # for each found match, try to narrow down match to a specific type
            for match in iterator:
                token_type = None

                for token_regex in token_types:
                    single_match = re.match(token_regex[0], match.group(0))
                    if single_match:
                        token_type = token_regex[1]
                        break

                if not token_type:
                    # token without type: error!
                    raise Exception('`{}` could not be parsed.'.format(match.group(0)))

                tokens.append((single_match.group(0), token_type, line_num + 1))

    # print out table
    print('token,classification,line')
    for token in tokens:
        print('{},{},{}'.format(token[0], token[1], token[2]))
