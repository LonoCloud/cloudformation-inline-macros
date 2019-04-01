#!/usr/bin/env python3

# Import the mostly common modules
# This line should match import in snippit
#import copy, functools, json, math, os, random, re, string, sys, time, traceback, types
import copy, functools, json, math, os, re, string, sys, time, traceback, types

def definitions():
          global walk, mergewith, deepmerge, handler

#### vvv snip from here vvv ####

          import copy, functools, json, math, os, re, string, sys, time, traceback, types

          # Call f on every element of obj. Operates in either depth
          # first order (bf == false) or breadth first (bf == true).
          # The arguments to f depend on the element type:
          # - array element: f(val, idx, arr)
          # - object key:    f(key)
          # - object value:  f(val, key, keyIdx, keyList)
          #
          # Can used for a deep copy: walk(lambda v, *a: v, obj)
          def walk(f, obj, bf=False):
              if not (isinstance(obj, dict) or isinstance(obj, list)): return obj
              if bf: # breadth first walk
                  if isinstance(obj, list):
                      newList = [f(v, i, obj) for [i, v] in enumerate(obj)]
                      return [walk(f, v, bf) for v in newList]
                  elif isinstance(obj, dict):
                      keyArr = [f(k) for k in sorted(obj.keys())]
                      kvs = [(k, f(obj[k], k, i, keyArr)) for [i, k] in enumerate(keyArr)]
                      return {k:walk(f, v, bf) for [k, v] in kvs}
              else: # depth first walk
                  if isinstance(obj, list):
                      return [f(walk(f, v, bf), i, obj) for [i, v] in enumerate(obj)]
                  elif isinstance(obj, dict):
                      keyArr = sorted(obj.keys())
                      newMap = {}
                      for [i, k] in enumerate(keyArr):
                          x = f(walk(f, obj[k], bf), k, i, keyArr)
                          newMap[f(k)] = x
                      return newMap

          # Merge two maps using the result of f(v1, v2) for any keys
          # that occur in both maps
          def mergewith(f, a, b):
            newMap = a.copy()
            for [k, v] in b.items():
                if k in newMap: newMap[k] = f(newMap[k], v)
                else:           newMap[k] = v
            return newMap

          # Deep merge two maps
          def deepmerge(a, b):
            if a and isinstance(a, dict): return mergewith(deepmerge, a, b)
            else:                         return b


          # If obj contains 'Fn::Macro', invoke the macros using
          # the current fragment and substitute resulting fragment
          # Fn::Macro can contain one call (map) or multiple (list)
          def doMacro(event, context, obj):
              while isinstance(obj, dict) and obj.get('Fn::Macro'):
                  mc = obj['Fn::Macro']
                  res = walk(lambda v, *a: v, obj) # deep copy
                  del res['Fn::Macro']
                  if isinstance(mc, dict): mc = [mc]
                  for call in mc:
                      evt = event.copy()
                      evt.update({
                          'params': call.get('Parameters', {}),
                          'fragment': res })
                      res = globals()[call['Name']](evt, context)
                  obj = res
              return obj

          # If obj contains 'Fn::Function', call the first argument
          # as a global function using the remaining arguments.
          def doFunction(obj, *a):
              if isinstance(obj, dict) and obj.get('Fn::Function'):
                  fname, *fargs = obj['Fn::Function']
                  return globals()[fname](*fargs)
              return obj

          def handler(event, context):
              print( 'event:', json.dumps(event))
              resp = {'requestId': event['requestId'],
                      'status'   : 'success' }
              try:
                  frag = event['fragment']
                  if not 'AWSTemplateFormatVersion' in frag:
                      raise 'no AWSTemplateFormatVersion in template' 
                  preEvalDef = frag.get('Metadata', {}).get('PyEval', None)
                  macroDefs = frag.get('Metadata', {}).get('PyMacros', None)

                  # Expose utility functions in global scope
                  # TODO
                  
                  # Eval any PreEval code
                  if preEvalDef:
                    # locals defaults to globals if globals is set so
                    # everything is evaluted/defined in global context
                    exec(compile(preEvalDef, '', 'exec'), globals())

                  # Instantiate macros into global handler functions
                  if macroDefs:
                      for [k, v] in macroDefs.items():
                        code = "def %s(event, context):\n" % k
                        code += re.sub(r'^', '    ', v, flags=re.MULTILINE)
                        exec(compile(code, '', 'exec'))
                        globals()[k] = locals()[k]

                  # Do breadth first macro invocation (i.e. start with
                  # the top-level macros and work down the tree). This
                  # is unlike how standard CloudFormation macros work
                  # which is depth first, but it is more similar to
                  # Lisp macros.
                  frag = walk(lambda obj, *a, **kw: doMacro(event, context, obj),
                          [frag], True)[0]

                  # Do depth first invocation of functions
                  frag = walk(doFunction, [frag], False)[0]

                  # Return expected response object with new fragment
                  print('callback fragment:', json.dumps(frag))
                  resp['fragment'] = frag

              except Exception as e:
                  traceback.print_exc()
                  #print('caught error:', e)
                  resp['status'] = 'failure'
                  resp['errorMessage'] = str(e)
              return resp

#### ^^^ snip to here ^^^ ####

from cfn_flip import to_yaml, to_json

definitions()

mode = sys.argv[1]

def warn(*a, **kw):
    print(*a, file=sys.stderr, **kw)

def load(tPath):
    baseEvt = {
      'region': 'us-west-2',
      'accountId': 'some-account-id',
      'transformId': 'some-tx-id',
      'requestId': 'some-request-id',
      'params': {},
      'templateParameterValues': {}
    }

    fragment = json.loads(to_json(open(tPath).read()))
    tParams = {}
    for [k, v] in fragment.get('Parameters', {}).items():
        val = os.environ.get(k, v.get('Default', None))
        if (not val) and (val != ""):
            raise('Parameter %s is required' % k)
        if v['Type'] == 'CommaDelimitedList':
            tParams[k] = val and re.split(r" *, *", val) or []
        else:
            tParams[k] = val
    event = baseEvt.copy()
    event.update({
        'fragment': fragment,
        'templateParameterValues': tParams})
    resp = handler(event, {})
    for k in ['JSEval', 'JSMacros', 'PyEval', 'PyMacros']:
        if k in resp['fragment']['Metadata']:
            del resp['fragment']['Metadata'][k]
    return resp

def loadTest(tPath, cPath):
    warn("\nTESTING: expand of %s == %s" % (tPath, cPath))

    resp = load(tPath)

    expected = json.loads(to_json(open(cPath).read()))
    respFragment = resp['fragment'].copy()
    # Remove stuff we don't want to check/show
    del respFragment['Metadata']
    def ignorer(v, *a):
        if isinstance(v, str) and v.startswith('Ignore: '): return 'IGNORED'
        else: return v
    expected = walk(ignorer, expected)
    respFragment = walk(ignorer, respFragment)
    try:
        assert expected == respFragment
        warn('MATCH: expanded %s == %s' % (tPath, cPath))
    except Exception as e:
        warn('MISMATCH: expanded %s != %s' % (tPath, cPath))
        warn(json.dumps(respFragment))
        warn(json.dumps(expected))
        warn('FAILURE')
        sys.exit(1)
    warn('SUCCESS')

if mode == 'load':
    warn(to_yaml(json.dumps(load(sys.argv[2])['fragment'])))
elif mode == 'compare':
    loadTest(sys.argv[2], sys.argv[3])
elif mode == 'test':
    #
    # walk tests
    #
    frag = {
      'region': 'us-west-2',
      'templateParameterValues': [
        {'abc': {'def': 'ghi'}},
        {'jkl': {'mno': 'pqr'}} ] }

    log = []
    warn("TESTING walk depth first")
    warn("FRAG:", json.dumps(frag))
    res = walk(lambda v, *a: log.append(v) or v, frag, False)
    warn("RES: ", json.dumps(res))
    warn("LOG:", json.dumps(log))
    assert frag == res
    assert len(log) == 14
    assert log == ["us-west-2","region","ghi","def",{"def":"ghi"},"abc",{"abc":{"def":"ghi"}},"pqr","mno",{"mno":"pqr"},"jkl",{"jkl":{"mno":"pqr"}},[{"abc":{"def":"ghi"}},{"jkl":{"mno":"pqr"}}],"templateParameterValues"]
    warn('SUCCESS')

    log = []
    warn("\nTESTING walk breadth first")
    warn("FRAG:", json.dumps(frag))
    res = walk(lambda v, *a: log.append(v) or v, frag, True)
    warn("RES: ", json.dumps(res))
    warn("LOG:", json.dumps(log))
    assert frag == res
    assert len(log) == 14
    assert log == ["region","templateParameterValues","us-west-2",[{"abc":{"def":"ghi"}},{"jkl":{"mno":"pqr"}}],{"abc":{"def":"ghi"}},{"jkl":{"mno":"pqr"}},"abc",{"def":"ghi"},"def","ghi","jkl",{"mno":"pqr"},"mno","pqr"]
    warn('SUCCESS')

    frag = {
      "Type": "Number",
      "Value": {
        "Fn::Function": [ "Add", 2, {
            "Fn::Function": [ "Mult", 3, 4 ] } ] } }
    log = []
    warn("\nTESTING walk depth first")
    warn("FRAG:", json.dumps(frag))
    res = walk(lambda v, *a: log.append(v) or v, frag, False)
    warn("RES: ", json.dumps(res))
    warn("LOG:", json.dumps(log))
    assert frag == res
    assert len(log) == 14
    assert log == ["Number","Type","Add",2,"Mult",3,4,["Mult",3,4],"Fn::Function",{"Fn::Function":["Mult",3,4]},["Add",2,{"Fn::Function":["Mult",3,4]}],"Fn::Function",{"Fn::Function":["Add",2,{"Fn::Function":["Mult",3,4]}]},"Value"]
    warn('SUCCESS')

    #
    # merge tests
    #

    m1 = {"a": 1, "b": 2}
    m2 = {"a": 9, "b": 98, "c": 0}
    warn("\nTESTING mergewith add:", json.dumps(m1), json.dumps(m2))
    res = mergewith(lambda a, b: a+b, m1, m2)
    warn("RES:", json.dumps(res))
    assert res == {"a": 10, "b": 100, "c": 0}
    warn('SUCCESS')

    m1 = {"a": {"b": 3, "c": 4}}
    m2 = {"a": {"b": 5}}
    warn("\nTESTING deepmerge:", json.dumps(m1), json.dumps(m2))
    res = deepmerge(m1, m2)
    warn("RES:", json.dumps(res))
    assert res == {"a": {"b": 5, "c": 4}}
    warn('SUCCESS')

    #
    # Before and After Compare tests
    #
    tests = [['tests/t1.yaml', 'tests/t1-result.yaml'],
             ['tests/t2.yaml', 'tests/t2-result.yaml'],
             ['tests/t3.yaml', 'tests/t3-result.yaml'],
             ['tests/t4.yaml', 'tests/t4-result.yaml'],
             ['tests/t5.yaml', 'tests/t5-result.yaml']]
    for [tPath, cPath] in tests:
        loadTest(tPath, cPath)
else:
    print("Unknown mode %s" % mode)
    sys.exit(1)

