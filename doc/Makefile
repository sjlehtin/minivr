.PHONY : all minivr.sql clean

.INTERMEDIATE : minivr.sql

all: minivr.pdf

minivr.sql:
	../devsite/manage.py sqlall minivr > $@

minivr.pdf: minivr.sql

%.pdf %.aux %.log %.out %.toc %.lol %.lof: %.tex
	-pdflatex -draftmode -interaction batchmode -halt-on-error $<
	pdflatex -interaction nonstopmode -halt-on-error $<

clean:
	rm -f minivr.aux minivr.log minivr.out minivr.toc minivr.pdf minivr.lol minivr.lof
