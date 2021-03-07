HTML=tutorial.html developers-guide.html

all: $(HTML)

clean:
	rm -f $(HTML)

%.html: %.rst
	python makedocs.py < $< > $@

