# Lono InlineJS/InlinePy Tutorial

This tutorial describes how to write macros starting from some very
simple macros and moving to more complex macros. The full Yaml
template files that demonstrate each example can be found in the
`examples/` directory. Each example has both a InlineJS JavaScript and
InlinePy Python example template named `*-js.yaml` and `*-py.yaml`
respectively.

InlineJS JavaScript macros are declared within the JSMacros subsection
of the Metadata section of a CloudFormation template. Likewise,
InlinePy Python macros are declared within the PyMacros subsection of
the Meatadata section.

The inline macro code is called with the same top-level parameters as
a regular CloudFormation macro call: event, and context.  The event
parameter has the following structure:

```js
{
  region: ...,                  // region where macro resides
  accountId: ...,               // invoking account ID
  fragment: ...,                // sibling template fragment (JSON)
  transformId: ...,             // name of macro invoking this function
  params: ...,                  // specified parameters
  requestId: ...,               // ID of request
  templateParameterValues: ..., //
}
```

The three most important attributes are `fragment`, `params`, and
`templateParameterValues`. The `fragment` attribute contains the
fragment of the template where the macro call occurs including all
sibling elements. The `params` attibute contains the Parameters that
were used in the macro call. The `templateParameterValues` attribute
contains a map of the top-level template parameters (after they have
been resolved).

The return fragment value of the macro call will become the new value
of the template at the position where the macro is called. This is
slightly different from normal CloudFormation which return a response
object containing the fragment. The Inline\* system handles the
creation of the response object automatically. In addition, InlineJS
are different from CloudFormation macros in that they do not use
a callback function but just return the new fragment directly.

Note that the returned fragment will replace the entire fragment at
the point in the template where the macro is called and this includes
all sibling values. If the macro wants to preserve sibling values it
must merge these from original fragment (from the event arguemnt) with
the new fragment that is returned.


## Example 1: Trivial Macro

Here is a full template that contains the definition and call of
a trivial InlineJS JavaScript macro:

```yaml
AWSTemplateFormatVersion: "2010-09-09"
Description: Example 1 - trivial example
Transform: [InlineJS-1_0]

Metadata:
  JSMacros:
    Foo: |
        console.warn(event)
        return "bar"

Resources: {}

Outputs:
  MyOutput:
    Value:
      'Fn::Macro':
        - Name: Foo
```

The Foo macro uses the `|` Yaml syntax to include a idented multiline
string value containing the source of the macro. The Foo macro first
logs the event argument then returns a fragment containing only the
string "bar". This string will be inserted into the template at the
point where the macro is called. This result is that the "MyOutput"
output will be set to the string "bar" that was returned from the
macro call.

We can use command line testing tool to see what will happen
when the InlineJS macros are run/resolved:

```yaml
$ ./lono-inline-1.0.js load examples/e1-trivial-js.yaml
{ region: 'us-west-2',
  accountId: 'some-account-id',
  transformId: 'some-tx-id',
  requestId: 'some-request-id',
  params: {},
  templateParameterValues: {},
  fragment: {} }
AWSTemplateFormatVersion: '2010-09-09'
Description: Example 1 - trivial example
Transform:
  - InlineJS-1_0
Metadata: {}
Resources: {}
Outputs:
  MyOutput:
    Value: bar
```

The first part of the output is the event parameter printed by the
`console.warn`. When the template is actually evaluated in
CloudFormation the log output will be stored in the CloudWatch log
stream for the underlying InlineJS macro.

The second part of the output is the final template after the the
InlineJS macros have been resolved. Note that `MyOutput` output now
has a value that is just "bar" in place of the macro call.


## Example 2: Simple Loop

If you have used CloudFormation templates "in anger" you will soon run
into a situation where you would like to repeat a section of the
template with identical or similar data. Here a snippit of a template
with a simple looping macro:

```yaml
Metadata:
  JSMacros:
    Loop: |
        const { fragment, params: {Prefix, Fragment, Count} } = event
        for (let i = 1; i <= Count; i++) {
            Object.assign(fragment, {[Prefix+i]: Fragment})
        }
        return fragment

Outputs:
  'Fn::Macro':
    Name: Loop
    Parameters:
      Prefix: "MyOutput"
      Count: 3
      Fragment:
        Value: "An output value"
```

The `AWSTemplateFormatVersion`, `Description`, and `Transform` fields
have been elided from the above template snippit. These fields will
continue to be elided in subsequent examples.

Here is the Outputs section that results from evaluating the above
template:

```yaml
$ ./lono-inline-1.0.js load examples/e3-loop-js.yaml
...
Outputs:
  MyOutput1:
    Value: An output value
  MyOutput2:
    Value: An output value
  MyOutput3:
    Value: An output value
```

The Loop macro repeats content in the returned fragment. The Loop
macro makes use of a new `Parameters` key. This data becomes the
`params` attribute in the `event` parameter when the macro is called.
The `Prefix` parameter specifies the string that will be combined with
the current index number to form the element key name. The `Count`
parameter specifies how many time the elements should be repeated.
Finally, the Fragment parameter specifies what the content will be of
each repeated element.


## Example 3: Simple Conditional

Consider the following template:

```yaml
Parameters:
  CondParam:
    Type: String
    Default: "yes"

Metadata:
  JSMacros:
    Conditional: |
        const { fragment, templateParameterValues, params: {Fragment} } = event
        if (templateParameterValues.CondParam in {"yes":1,"true":1}) {
            Object.assign(fragment, Fragment)
        }
        return fragment

Outputs:
  FixedOutput:
    Value: a fixed output value

  'Fn::Macro':
    Name: Conditional
    Parameters:
      Fragment:
        ConditionalOutput:
          Value: "An conditional output value"
```

The `Conditional` macro has a similar implementation to the `Loop`
macro but instead of repeating a fragment, it either returns the
fragment or omits the fragment entirely depending on the setting of
a top-level template parameter. The `templateParameterValues`
attribute of the `event` parameter contains a map of the resolved
template parameters. If the `CondParam` is set to "yes" or "true" then
the `Fragment` value from the macro parameters will be merged into the
returned fragment otherwise the original fragment is returned without
conditional `Fragment`.

One other thing to note is that the macro is written to preserve any
sibling elements of the macro call. In this case the `FixedOutput`
sibling value is preserved in the result.

Here is the result of evaluating the template with the `CondParam`
parameter enabled (set to "yes"):

```yaml
$ CondParam=yes ./lono-inline-1.0.js load examples/e4-conditional-js.yaml
...
Outputs:
  FixedOutput:
    Value: a fixed output value
  ConditionalOutput:
    Value: An conditional output value
```

Here is the result of evaluating the template with the `CondParam`
parameter disabled (set to "no"):

```yaml
$ CondParam=no ./lono-inline-1.0.js load examples/e4-conditional-js.yaml
...
Outputs:
  FixedOutput:
    Value: a fixed output value
```

## Example 4: Inline Functions

In addition to user defined inline macros, Inline\* also supports user
defined inline functions. Functions are defined in within the
`Metadata` section in `JSInit` and `PyInit` (respectively for InlineJS
and InlinePy). To make functions in `JSInit` available they must be
added to the global `exports` variable (similar to how Node.js modules
do function exports). Any top-level functions declared in `PyInit` are
available to be called (similar to python modules).

Here is a template that show `Add` and `Mult` functions that enable
addition and multiplication to be used within a template:

```yaml
Metadata:
  JSInit: |
      function Add(a, b) { return a + b }
      function Mult(a, b) { return a * b }
      Object.assign(exports, {Add, Mult})

Outputs:
  Output:
    Value: !Function [Add, 5, !Function [Mult, 6, 7] ]
```

The result of evaluating this template is:

```yaml
$ ./lono-inline-1.0.js load examples/e5-functions-js.yaml
...
Outputs:
  Output:
    Value: 47
```

Differences between macros and functions
* Macro calls are evaluated breadth first (outside in until there are
  no more macro calls). After all macros are evaluated then functions
  are evaluated depth first (inside out). Function calls can make use
  of the result of other function calls.
* Each macro is defined separately as a unique attribute under
  `JSMacros` or `PyMacros` sections in the `Metadata` section.
  Function definitions happen in the single `JSInit` or `PyInit`
  section under `Metadata`.
* Macro definitions have implicit parameters `event` and `context`.
  Functions definitions are defined as normal JavaScript or Python
  functions with user defined parameters.
* Macro calls are passed a map that contains `Name` and optionally
  `Parameters` (which becomes the `params` attribute of event).
  Function calls take a sequence of the function name (as a string)
  followed by positional parameters (only positional parameters are
  supported in Python functions).


...

### Note about Python Modules

In InlinePy macro and function code definitions, the following modules
are already imported and automatically available: copy, functools,
json, math, os, re, string, sys, time, traceback, types.  Other
modules can be imported in the PyInit code section and then later used
in PyMacro defintions.


## Example 5: Loop over a Parameter List

Now lets consider a slightly more complex macro:

```yaml
Parameters:
  List1:
    Type: CommaDelimitedList
    Default: "Abc, Def"

  List2:
    Type: CommaDelimitedList
    Default: "Foo, Bar, Baz"

Metadata:
  JSMacros:
    ParamLoop: |
        const { fragment, params: {Param, Fragment} } = event
        for (let item of event.templateParameterValues[Param]) {
          Object.assign(fragment, walk(
            v => typeof v === 'string' ? v.replace(/%/, item) : v,
            Fragment))
        }
        return fragment

Outputs:
  'Fn::Macro':
    - Name: ParamLoop
      Parameters:
        Param: List1
        Fragment:
          List1Output%:
            Value: "List1Output% value"
    - Name: ParamLoop
      Parameters:
        Param: List2
        Fragment:
          List2Output%:
            Value: "List2Output% value"
```

The `ParamLoop` macro loops over the values from a template parameter
and uses those values to templatize strings within the new fragment.
There are several new concepts introduced by the template above:

* The `ParamLoop` macro loops over parameter values of the
  "CommaDelimitedList" type. Note that CloudFormation expands those
  types of parameters into actual lists by the time they are passed in
  the `templateParameterValues` attribute of the `event` parameter.
* The `walk` function is a utility function provided by the InlineJS
  and InlinePy macro system. `ParamLoop` uses the `walk` utility
  function to replace all occurences of "%" within strings in the
  `Fragment` with the current loop element value.
* Prior example had a macro call map directly beneath the "Fn::Macros"
  key. This example has a list of two macro calls within a single
  "Fn::Macros" tag. This alternate means of specifying macro calls
  allows two different macro calls to be made at the same point in the
  template tree. The macros calls are made sequentially with the
  result fragment from the earlier macro passed as the input fragment
  to the next macro. The result of the final macro calls becomes the
  fragment that is inserted into the tree.


## Example 6: Merge with a Fragment Class

There is a certain class of macros that want to access template
context that is outside (above) the point in the template where the
macro would like to actually make modifications. The Inline\* macros
are themselves examples of this type of higher level macro
functionality. Here is an example of a macro that enables local
modification but still has access to the broader template context:

```yaml
Metadata:
  JSMacros:
    Merger: |
        return walk((v) => {
            if (v && v.constructor === Object && 'Merge' in v) {
                cfrag = event.fragment.Metadata.Classes[v.Merge]
                delete v.Merge
                return deepMerge(cfrag, v)
            }
            return v
        }, event.fragment)

  Classes:
    SSMString:
      Type: 'AWS::SSM::Parameter'
      Properties:
        Type: String
        Value: default class value

'Fn::Macro':
  Name: Merger

Resources:
    SSM1:
      Merge: SSMString
      Properties:
        Value: SSM1 Value

    SSM2:
      Merge: SSMString
      Properties:
        Value: SSM2 Value
```

The `Merger` macro defines a meta-macro (or perhaps meta-meta-macro)
that merges in default values into a point in the template based on
"classes" that are defined in the Metadata. The `Merger` macro must be
invoked from the very top-level of the template. It walks the tree
looking for keys that equal "Merge". For each point in the template
where it find this key, it uses the value of that key to look up
a base "class" from the `Classes` metadata sub-tree. It then uses this
class as default values which are then that are merged under the
existing values at point in the tree. The merge is done using the
`deepMerge` utility function that is provided by InlineJS (`deepmerge`
in InlinePy).

Here is the result of evaluating the above template:

```yaml
$ ./lono-inline-1.0.js load examples/e7-merge-class-js.yaml
...
Resources:
  SSM1:
    Type: 'AWS::SSM::Parameter'
    Properties:
      Type: String
      Value: SSM1 Value
  SSM2:
    Type: 'AWS::SSM::Parameter'
    Properties:
      Type: String
      Value: SSM2 Value
```

In the evaluated result, the two "Type" keys came from the class but
the "Value" came from the original "call point" and overrides the
default value from the class.




