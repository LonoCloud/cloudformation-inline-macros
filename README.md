# InlineJS/InlinePy Cloudformation Macros

## Description

The lono-inline-1.0.yaml template defines a "meta" macro system that
allows cloudformation macros to be define within the same template in
which they are used. This is done by defining macros in the Metadata
section which can then be called with 'Fn::Macro' definitions within
the template.

The lono-inline-1.0.yaml template contains defintions for both the
JavaScript and Python versions of the macro. Copies of the JavaScript
and Python code respectively are contained in lono-inline-1.0.js and
lono-inline-1.0.py. The code in the yaml and js/py files should be
kept in sync.

## Command line usage/testing

The lono-inline-1.0.\* scripts have wrapper
code that present a command line interface for being able to test the
evaluation of macro code on a template. For example, this will show
the result of using the InlineJS macro on a template file:

```
cd modules/lono-inline
./lono-inline-1.0.js load ./lono-inline-1.0-test1.yaml
```

## Unit tests

Unit tests for the Inline\* macros can be executed like this:

```
cd modules/lono-inline
./lono-inline-1.0.js walk
./lono-inline-1.0.js merge
./lono-inline-1.0.js eval
./lono-inline-1.0.py walk
./lono-inline-1.0.py merge
./lono-inline-1.0.py eval
```

