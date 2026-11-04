CXX ?= g++
NCBITEXTLIB=** location of NCBITextLib **
LIBPATH=./lib
OS=-g -std=c++11
# OS=-O


.KEEP_STATE:

%:%.o
	$(CXX) $(OS) -o $@ $< -L$(LIBPATH) -lAb3P -L$(NCBITEXTLIB)/lib -lText

%.o: %.C
	$(CXX) -c $(OS) -I$(LIBPATH) -I$(NCBITEXTLIB)/include $< -o $@

all:
	$(MAKE) programs
	$(MAKE) data

programs:
	$(MAKE) library
	$(MAKE) make_wordSet
	$(MAKE) make_wordCountHash
	$(MAKE) identify_abbr
	$(MAKE) identify_abbr_jsonl

library:
	$(MAKE) -C lib

data:
	./make_wordSet WordData/stop stop
	./make_wordSet WordData/Lf1chSf Lf1chSf
	./make_wordCountHash WordData/SingTermFreq.dat


test:
	./identify_abbr MED1250_unlabeled | diff identify_abbr-out -

test2:
	./identify_abbr test2.in | diff test2.out -

clean:
	$(MAKE) -C lib clean
	rm -f WordData/cshset_* WordData/hshset_*
	rm -f identify_abbr identify_abbr_jsonl make_wordCountHash make_wordSet *.o *~

make_wordSet:		make_wordSet.o
make_wordCountHash:	make_wordCountHash.o
identify_abbr:		identify_abbr.o lib/libAb3P.a
identify_abbr.o:	lib/Ab3P.h
identify_abbr_loc:	identify_abbr.o lib/libAb3P.a
identify_abbr_loc.o:	lib/Ab3P.h

identify_abbr_jsonl: identify_abbr_jsonl.o lib/libAb3P.a
identify_abbr_jsonl.o: lib/Ab3P.h
