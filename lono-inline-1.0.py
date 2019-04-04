#!/usr/bin/env python3

# Import the mostly common modules
# This line should match import in snippit
import copy, functools, importlib, json, math, os, re, string, sys, time, traceback, types

def definitions():
          global walk, mergewith, deepmerge, handler

#### vvv snip from here vvv ####

          import copy, functools, importlib, json, math, os, re, string, sys, time, traceback, types

          # Call f on every node of obj. Depth first unless bf is
          # true. The arguments to f depend on the element type:
          # - array element: f(val, idx, arr)
          # - object key:    f(key)
          # - object value:  f(val, key, keyIdx, keyList)
          def walk(f, obj, bf=False):
            if not isinstance(obj, (dict, list)): return obj
            if bf: # breadth first walk
              if isinstance(obj, list):
                newList = [f(v, i, obj) for [i, v] in enumerate(obj)]
                return [walk(f, v, bf) for v in newList]
              elif isinstance(obj, dict):
                keys = [f(k) for k in sorted(obj.keys())]
                kvs = [(k, f(obj[k], k, i, keys)) for [i, k] in enumerate(keys)]
                return {k:walk(f, v, bf) for [k, v] in kvs}
            else: # depth first walk
              if isinstance(obj, list):
                return [f(walk(f, v, bf), i, obj) for [i, v] in enumerate(obj)]
              elif isinstance(obj, dict):
                keys = sorted(obj.keys())
                m = {}
                for [i, k] in enumerate(keys):
                  x = f(walk(f, obj[k], bf), k, i, keys)
                  m[f(k)] = x
                return m

          # Merge using f(v1, v2) for keys that occur in both maps
          def mergewith(f, a, b):
            return {**a, **{k: (f(a[k], v) if k in a else v)
                for k,v in b.items()}}

          # Deep merge two maps
          def deepmerge(a, b):
            return mergewith(deepmerge, a, b) if isinstance(a, dict) else b

          # If obj contains 'Fn::Macro', invoke the macros using
          # the current fragment and substitute resulting fragment
          # Fn::Macro can contain one call (map) or multiple (list)
          def doMacro(ns, event, context, obj):
            while isinstance(obj, dict) and 'Fn::Macro' in obj:
              mc = obj['Fn::Macro']
              res = walk(lambda v, *a: v, obj) # deep copy
              del res['Fn::Macro']
              for call in [mc] if isinstance(mc, dict) else mc:
                event = {**event,
                         **{'params': call.get('Parameters', {}), 'fragment': res}}
                res = ns[call['Name']](event, context)
              obj = res
            return obj

          # If obj contains 'Fn::Function', call the first argument
          # as a function using the remaining arguments.
          def doFunction(ns, obj, *a):
            if isinstance(obj, dict) and 'Fn::Function' in obj:
              fname, *fargs = obj['Fn::Function']
              return ns[fname](*fargs)
            return obj

          def handler(event, context):
            print('event:', json.dumps(event))
            resp = {'requestId': event['requestId'], 'status': 'success'}
            try:
              frag = event['fragment']
              assert 'AWSTemplateFormatVersion' in frag, 'AWSTemplateFormatVersion missing'
              meta = frag.get('Metadata', {})
              importDef = meta.get('PyImports', [])
              initDef = meta.get('PyInit', None)
              macroDefs = meta.get('PyMacros', {})

              ns = {} # user macro and function definitions

              # Additional imports
              for imp in importDef:
                globals()[imp] = importlib.import_module(imp)

              # Run initDef with locals set to ns
              if initDef:
                gtmp = {**globals(), **{'event':  event, 'context': context}}
                exec(compile(initDef, '', 'exec'), gtmp, ns)

              # Instantiate macros in ns
              for [k, v] in macroDefs.items():
                code = "def %s(event, context):\n" % k
                code += re.sub(r'^', '  ', v, flags=re.MULTILINE)
                exec(compile(code, '', 'exec'))
                ns[k] = locals()[k]

              # Do breadth first macro invocation (outside in). This
              # is unlike standard CFN macros which are depth first,
              # but more similar to Lisp macros.
              frag = walk(lambda obj, *a: doMacro(ns, event, context, obj),
                  [frag], True)[0]

              # Do depth first invocation of functions
              frag = walk(lambda *a: doFunction(ns, *a), [frag], False)[0]

              # Response object with new fragment
              print('new fragment:', json.dumps(frag))
              resp['fragment'] = frag

            except Exception as e:
              traceback.print_exc()
              resp['status'] = 'failure'
              resp['errorMessage'] = str(e)
            return resp

#### ^^^ snip to here ^^^ ####

from cfn_flip import to_yaml, to_json

mode = sys.argv[1]
VERBOSE = os.environ.get('VERBOSE', None)

definitions()

if not VERBOSE:
    orig_print = print
    def print(*args, **kw):
        if kw.get('file') == sys.stderr:
            orig_print(*args, **kw)

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
    if resp['status'] == 'success':
        for k in ['JSInit', 'JSMacros', 'PyInit', 'PyMacros']:
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
    res = load(sys.argv[2])
    print(res)
    if res['status'] != 'success': sys.exit(1)
    warn(to_yaml(json.dumps(res['fragment'])))
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
    print("LOG:", json.dumps(log))
    assert frag == res
    assert len(log) == 14
    assert log == ["us-west-2","region","ghi","def",{"def":"ghi"},"abc",{"abc":{"def":"ghi"}},"pqr","mno",{"mno":"pqr"},"jkl",{"jkl":{"mno":"pqr"}},[{"abc":{"def":"ghi"}},{"jkl":{"mno":"pqr"}}],"templateParameterValues"]
    warn('SUCCESS')

    log = []
    warn("\nTESTING walk breadth first")
    warn("FRAG:", json.dumps(frag))
    res = walk(lambda v, *a: log.append(v) or v, frag, True)
    warn("RES: ", json.dumps(res))
    print("LOG:", json.dumps(log))
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
    print("LOG:", json.dumps(log))
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
    warn("Unknown mode %s" % mode)
    sys.exit(1)

