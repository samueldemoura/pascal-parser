python3 pascalparser.py $1 > tmp.csv
python3 pascalanalyzer.py tmp.csv
rm tmp.csv
