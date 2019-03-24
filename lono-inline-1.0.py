#!/usr/bin/env python3

# this line should match import in snippit
import sys, os, re, json, traceback

def definitions():
          global walk, handler

#### vvv snip from here vvv ####

          import sys, os, re, json, traceback

          # Call f on every element of obj. Operates in either depth
          # first order (bf == false) or breadth first (bf == true).
          # The arguments to f depend on the element type:
          # - array element: f(val, idx, arr)
          # - object key:    f(key)
          # - object value:  f(val, key, keyIdx, keyList)
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

          # If obj contains 'Fn::Macro', invoke the macros using
          # the current fragment and substitute resulting fragment
          # Fn::Macro can contain one call (map) or multiple (list)
          def doMacro(event, context, obj):
              if isinstance(obj, dict) and obj.get('Fn::Macro'):
                  mc = obj['Fn::Macro']
                  del obj['Fn::Macro']
                  res = obj
                  if isinstance(mc, dict): mc = [mc]
                  for call in mc:
                      evt = event.copy()
                      evt.update({
                          'params': call.get('Parameters', {}),
                          'fragment': res })
                      res = globals()[call['Name']](evt, context)
                  return res
              else:
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

if mode == 'walk':
    frag = {
      'region': 'us-west-2',
      'templateParameterValues': [
        {'abc': {'def': 'ghi'}},
        {'jkl': {'mno': 'pqr'}} ] }

    log = []
    print("TESTING walk depth first")
    print("FRAG:", json.dumps(frag))
    res = walk(lambda v, *a: log.append(v) or v, frag, False)
    print("RES: ", json.dumps(res))
    print("LOG:", json.dumps(log))
    assert frag == res
    assert len(log) == 14
    assert log == ["us-west-2","region","ghi","def",{"def":"ghi"},"abc",{"abc":{"def":"ghi"}},"pqr","mno",{"mno":"pqr"},"jkl",{"jkl":{"mno":"pqr"}},[{"abc":{"def":"ghi"}},{"jkl":{"mno":"pqr"}}],"templateParameterValues"]

    log = []
    print("\nTESTING walk breadth first")
    print("FRAG:", json.dumps(frag))
    res = walk(lambda v, *a: log.append(v) or v, frag, True)
    print("RES: ", json.dumps(res))
    print("LOG:", json.dumps(log))
    assert frag == res
    assert len(log) == 14
    assert log == ["region","templateParameterValues","us-west-2",[{"abc":{"def":"ghi"}},{"jkl":{"mno":"pqr"}}],{"abc":{"def":"ghi"}},{"jkl":{"mno":"pqr"}},"abc",{"def":"ghi"},"def","ghi","jkl",{"mno":"pqr"},"mno","pqr"]

    frag = {
      "Type": "Number",
      "Value": {
        "Fn::Function": [ "Add", 2, {
            "Fn::Function": [ "Mult", 3, 4 ] } ] } }
    log = []
    print("\nTESTING walk depth first")
    print("FRAG:", json.dumps(frag))
    res = walk(lambda v, *a: log.append(v) or v, frag, False)
    print("RES: ", json.dumps(res))
    print("LOG:", json.dumps(log))
    assert frag == res
    assert len(log) == 14
    assert log == ["Number","Type","Add",2,"Mult",3,4,["Mult",3,4],"Fn::Function",{"Fn::Function":["Mult",3,4]},["Add",2,{"Fn::Function":["Mult",3,4]}],"Fn::Function",{"Fn::Function":["Add",2,{"Fn::Function":["Mult",3,4]}]},"Value"]


elif mode == 'merge':
    pass
elif mode == 'eval':
    pass
elif mode == 'load':
    baseEvt = {
      'region': 'us-west-2',
      'accountId': 'some-account-id',
      'transformId': 'some-tx-id',
      'requestId': 'some-request-id',
      'params': {},
      'templateParameterValues': {}
    }

    for tPath in sys.argv[2:]:
        print("*** LOADING: %s" % tPath)
        fragment = json.loads(to_json(open(tPath).read()))
        tParams = {}
        for [k, v] in fragment.get('Parameters', {}).items():
            val = os.environ.get(k, v.get('Default', None))
            tParams[k] = val
            if v['Type'] == 'CommaDelimitedList':
                tParams[k] = re.split(r" *, *", val)
        event = baseEvt.copy()
        event.update({
            'fragment': fragment,
            'templateParameterValues': tParams})
        resp = handler(event, {})
        print('*** RESULT: resp:')
        print(to_yaml(json.dumps((resp))))
else:
    print("Unknown mode %s" % mode)
    sys.exit(1)

