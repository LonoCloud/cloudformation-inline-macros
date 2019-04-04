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

The [tutorial](tutorial.md) describes how to write macros starting
from some very simple macros to more complex macros.

## Security Caveat

Short version: **You should only use the Inline\* system if you trust
all other users of the Inline\* system within your AWS account**.

Longer version: CloudFormation macros are defined using Lambda
functions. For performance reasons, when the samme Lambda function is
called mutliple times in close temporal proximity, the running state
of the lamba function is re-used. For example, if a Node.js Lambda
function defines anything in the global state variable, this state may
still appear in subsequent calls of the same Lambda function. This
same behavior applies to CloudFormation macro calls.

The use of Inline\* magnifies the potential impact of this behavior
because the deployment of a template that uses Inline\* could affect
subsequent deployments of templates that also use Inline\*. The design
of Inline\* attempts to prevent unintentional effects between template
deployments. However, it does not protect against intentional or
malicious attacks.


## Command line usage

The lono-inline-1.0.\* scripts have wrapper
code that present a command line interface for being able to test the
evaluation of macro code on a template. For example, this will show
the result of using the Inline* macro on a template file:

```
./lono-inline-1.0.js load ./tests/t1.yaml
./lono-inline-1.0.py load ./tests/t1.yaml
```

## CloudFormation Evaluation Process

When a CloudFormation template is deployed it goes through a number of
evaluation/expansion phases that happen in the following order:

* Template Parameters are evaluated.
* Template macros are evaluated. Normal template macros are evaluated
  depth-first (inside-out). Top-level macros (Transform) are evaluated
  last in left-to-right order. If the InlineJS macro is
  specified in the top-level Transform key then it triggers the
  following evaluation process:
  * Code in Metadata.JSInit is evaluated.
  * InlineJS macro calls are evaluated breadth-first (outside-in)
  * InlineJS function calls are evaluated depth-first (inside-out)

  If the InlinePy macro is specified in the top-level Transform key
  then it triggers the following evaluation process:
  * Any python modules listed in Metadata.PyModules is imported as
    a global module.
  * Code in Metadata.PyInit is evaluated.
  * InlinePy macro calls are evaluated breadth-first (outside-in)
  * InlinePy function calls are evaluated depth-first (inside-out)
* Conditionals are evaluated and resources with a false conditional
  are ignored in the next phase.
* Template Resources are created in dependency order. The dependency
  order is both explicit (using DependsOn creates dependencies) and
  implicit (Ref and GetAtt intrinsics create dependencies). Intrinsic
  functions are resolved during this phase.
* Template Outputs are generated

## Macro Definitions

Inline macros are defined in JSMacros and PyMacros sections of the
template metadata. Here is an example of a trivial InlineJS macro
definition that prints the event parameter and then returns an empty
map/dictionary:

```yaml
Metadata:
  JSMacros:
    Foo: |
        console.log(event)
        return {}
```

The inline macro code is called with the same top-level parameters as
a regular CloudFormation macro call: event, and context. The return
fragment value of the macro call will become the new value of the tree
at the position where the macro is called.


## Macro Calls

A InlineJS/InlinePy macro call be made from any point in the Yaml tree
under Resources or Outputs. A Macro call has the following structure:

```yaml
'Fn::Macro':
  Name: MacroName
  Parameters:
    Param1: "Param1 Value"
    Param2: "Param2 Value"
```

Alternately, multiple macro calls can be specified to happen
sequentially at the same point in the tree:

```yaml
'Fn::Macro':
  - Name: MacroName1
    Parameters:
      Param1: "Param1 Value"
      Param2: "Param2 Value"
  - Name: MacroName2
    Parameters:
      Param1: "Param1 Value"
      Param2: "Param2 Value"
```



## Unit tests

Unit tests for the Inline\* macros can be executed like this:

```
./lono-inline-1.0.js test
./lono-inline-1.0.py test
```

