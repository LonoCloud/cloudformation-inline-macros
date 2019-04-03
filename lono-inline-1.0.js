#!/usr/bin/env node
'use strict'

//// vvv snip from here vvv ////

          // Call f on every node of obj. Depth first unless bf is
          // true. The arguments to f depend on the element type:
          // - array element: f(val, idx, arr)
          // - object key:    f(key)
          // - object value:  f(val, key, keyIdx, keyList)
          function walk(f, obj, bf=false) {
            let x
            if (!obj || typeof(obj) !== 'object') { return obj }
            return bf
              ? Array.isArray(obj)
                ? obj.map((v, i, arr) => f(v, i, arr))
                   .map((v) => walk(f, v, bf))
                : Object.keys(obj)
                    .map((k) => f(k))
                    .map((k, i, arr) => [k, f(obj[k], k, i, arr)])
                    .reduce((a, [k, v]) => (a[k] = walk(f, v, bf), a), {})
              : Array.isArray(obj)
                ? obj.map((v, i, arr) => f(walk(f, v, bf), i, arr))
                : Object.keys(obj).reduce((a, k, i, arr) =>
                    (x = f(walk(f, obj[k], bf), k, i, arr), a[f(k)] = x, a), {})
          }

          // Merge using f(v1, v2) for keys that occur in both maps
          function mergeWith(f, a, b) {
            return Object.entries(b).reduce((m, [k, v]) =>
                (m[k] = k in m ? f(m[k], v) : v, m), Object.assign({}, a))
          }
          // Deep merge two maps
          function deepMerge(a, b) {
            return (a && a.constructor === Object) ? mergeWith(deepMerge, a, b) : b
          }


          // If obj contains 'Fn::Macro', invoke the macros using
          // the current fragment and substitute resulting fragment
          // Fn::Macro can contain one call (map) or multiple (list)
          function doMacro(ns, event, context, obj) {
            while (obj && typeof(obj) === 'object' && 'Fn::Macro' in obj) {
              const {['Fn::Macro']: mc, ...rest} = obj // split out calls
              let res = walk(v => v, rest) // deep copy
              obj = (Array.isArray(mc) ? mc : [mc])
                .reduce((res, call) =>
                  ns[call.Name](Object.assign({}, event, {
                    params: call.Parameters || {},
                    fragment: res
                  }), context),
                  res)
            }
            return obj
          }

          // If obj contains 'Fn::Function', call the first argument
          // as a function using the remaining arguments.
          function doFunction(ns, obj) {
            if (obj && typeof(obj) === 'object' && 'Fn::Function' in obj) {
              const [fname, ...fargs] = obj['Fn::Function']
              const fn = fname in ns ? ns[fname] : global[fname]
              return fn(...fargs)
            }
            return obj
          }

          exports.handler = function(event, context, callback) {
            console.log('event:', JSON.stringify(event))
            try {
              let frag = event.fragment
              if (!('AWSTemplateFormatVersion' in frag)) {
                throw new Error('AWSTemplateFormatVersion missing')
              }
              const initDef = frag.Metadata && frag.Metadata.JSInit
              const macroDefs = frag.Metadata && frag.Metadata.JSMacros || {}

              // Expose utility functions in global scope
              Object.assign(global, {walk, mergeWith, deepMerge})

              let ns = {} // user macro and function definitions

              // Run initDef with exports set to ns
              if (initDef) {
                const initFn = new Function('event', 'context', 'exports', initDef)
                initFn(event, context, ns)
              }

              // Instantiate macros in ns
              Object.entries(macroDefs).forEach(([k, v]) =>
                      ns[k] = new Function('event', 'context', v))

              // Do breadth first macro invocation (outside in). This
              // is unlike standard CFN macros which are depth first,
              // but more similar to Lisp macros.
              frag = walk(doMacro.bind(null, ns, event, context),
                      [frag], true)[0]

              // Do depth first invocation of functions
              frag = walk(doFunction.bind(null, ns), [frag], false)[0]

              // Response object with new fragment
              console.log('new fragment:', JSON.stringify(frag))
              callback(null, { requestId:  event.requestId,
                               status:     'success',
                               fragment:   frag })
            } catch (e) {
              console.error('caught error:', e)
              callback(e)
            }
          }

//// ^^^ snip to here ^^^ ////

//// vvv Local testing only vvv ///

const assert = require('assert')
const { readFileSync } = require('fs')
const { schema } = require('yaml-cfn')
const jsYaml = require('js-yaml')
const mode = process.argv[2]
const VERBOSE = process.env['VERBOSE']

/////////////////////////////////
// Add yaml types

let yamlTypeMacroMap = new jsYaml.Type('!Macro', {
    kind: 'mapping',
    construct: (data) => ({'Fn::Macro': data})
})
let yamlTypeMacroSeq = new jsYaml.Type('!Macro', {
    kind: 'sequence',
    construct: (data) => ({'Fn::Macro': data})
})
let yamlTypeFuncSeq = new jsYaml.Type('!Function', {
    kind: 'sequence',
    construct: (data) => ({'Fn::Function': data})
})
const inlineSchema = new jsYaml.Schema({
    include:  [schema],
    implicit: [],
    explicit: [yamlTypeMacroMap, yamlTypeMacroSeq, yamlTypeFuncSeq],
})

/////////////////////////////////

function die(code, ...args) { console.error(...args); process.exit(code) }

function load(tPath, callback) {
    const baseEvt = {
      region: 'us-west-2',
      accountId: 'some-account-id',
      transformId: 'some-tx-id',
      requestId: 'some-request-id',
      params: {},
      templateParameterValues: {}
    }

    const fragment = jsYaml.safeLoad(readFileSync(tPath, 'utf8'),
            {schema: inlineSchema})
    let tParams = {}
    for (const [k, v] of Object.entries(fragment.Parameters || {})) {
      const val = process.env[k] || v.Default
      if ((!val) && val !== "") { die(2, `Parameter ${k} is required`) }
      if (v.Type === 'CommaDelimitedList') {
        tParams[k] = val ? val.split(/ *, */) : []
      } else {
        tParams[k] = val
      }
    }

    const event = Object.assign({}, baseEvt,
            {fragment, templateParameterValues: tParams})
    exports.handler(event, {}, function (err, resp) {
        if (err) {
            callback(err, resp)
        } else {
            for (let k of ['JSInit', 'JSMacros', 'PyInit', 'PyMacros']) {
                delete resp.fragment.Metadata[k]
            }
            callback(err, resp)
        }
    })
}

function loadTest(tPath, cPath) {
  console.warn(`\nTESTING: expand of ${tPath} == ${cPath}`)
  load(tPath, function (err, resp) {
    if (err) {
      console.warn('ERROR:', err)
      console.warn("FAILURE")
      process.exit(1)
    }
    let expected = jsYaml.safeLoad(readFileSync(cPath, 'utf8'),
            {schema: inlineSchema})
    let respFragment = Object.assign({}, resp.fragment)
    // Remove stuff we don't want to check/show
    delete respFragment.Metadata
    let ignorer = v => typeof v === 'string' && v.startsWith('Ignore: ')
        ? 'IGNORED'
        : v
    expected = walk(ignorer, expected)
    respFragment = walk(ignorer, respFragment)
    try {
        assert.deepEqual(respFragment, expected)
        console.warn(`MATCH: expanded ${tPath} == ${cPath}`)
    } catch (e) {
        console.warn(`MISMATCH: expanded ${tPath} != ${cPath}`)
        console.warn(JSON.stringify(respFragment))
        console.warn(JSON.stringify(expected))
        console.warn("FAILURE")
        process.exit(1)
    }
    console.warn("SUCCESS")
  })
}


if (!VERBOSE) {
    console.log = (...a) => true
}

let res, log, frag, m1, m2
switch (mode) {
  case 'load':
    load(process.argv[3], function(err, resp) {
        if (err)  { process.exit(1) }
        console.warn(jsYaml.safeDump(resp.fragment,
                    {schema: inlineSchema}))
    })
    break
  case 'compare':
    loadTest(process.argv[3], process.argv[4])
    break
  case 'test':
    //
    // walk tests
    //
    frag = {
      region: 'us-west-2',
      templateParameterValues: [
        {abc: {def: 'ghi'}},
        {jkl: {mno: 'pqr'}} ] }

    log = []
    console.warn("TESTING walk depth first")
    console.warn("FRAG:", JSON.stringify(frag))
    res = walk((v, ...a) => (log.push(v), v), frag, false)
    console.warn("RES: ", JSON.stringify(res))
    console.log("LOG:", JSON.stringify(log))
    assert.deepEqual(frag, res)
    assert.equal(log.length, 14)
    assert.deepEqual(log, ["us-west-2","region","ghi","def",{"def":"ghi"},"abc",{"abc":{"def":"ghi"}},"pqr","mno",{"mno":"pqr"},"jkl",{"jkl":{"mno":"pqr"}},[{"abc":{"def":"ghi"}},{"jkl":{"mno":"pqr"}}],"templateParameterValues"])
    console.warn("SUCCESS")

    log = []
    console.warn("\nTESTING walk breadth first")
    console.warn("FRAG:", JSON.stringify(frag))
    res = walk((v, ...a) => (log.push(v), v), frag, true)
    console.warn("RES: ", JSON.stringify(res))
    console.log("LOG:", JSON.stringify(log))
    assert.deepEqual(frag, res)
    assert.equal(log.length, 14)
    assert.deepEqual(log, ["region","templateParameterValues","us-west-2",[{"abc":{"def":"ghi"}},{"jkl":{"mno":"pqr"}}],{"abc":{"def":"ghi"}},{"jkl":{"mno":"pqr"}},"abc",{"def":"ghi"},"def","ghi","jkl",{"mno":"pqr"},"mno","pqr"])
    console.warn("SUCCESS")

    frag = {
      "Type": "Number",
      "Value": {
        "Fn::Function": [ "Add", 2, {
          "Fn::Function": [ "Mult", 3, 4 ] } ] } }
    log = []
    console.warn("\nTESTING walk depth first")
    console.warn("FRAG:", JSON.stringify(frag))
    res = walk((v, ...a) => (log.push(v), v), frag, false)
    console.warn("RES: ", JSON.stringify(res))
    console.log("LOG:", JSON.stringify(log))
    assert.deepEqual(frag, res)
    assert.equal(log.length, 14)
    assert.deepEqual(log, ["Number","Type","Add",2,"Mult",3,4,["Mult",3,4],"Fn::Function",{"Fn::Function":["Mult",3,4]},["Add",2,{"Fn::Function":["Mult",3,4]}],"Fn::Function",{"Fn::Function":["Add",2,{"Fn::Function":["Mult",3,4]}]},"Value"])
    console.warn("SUCCESS")

    //
    // Merge tests
    //

    m1 = {a: 1, b: 2}
    m2 = {a: 9, b: 98, c: 0}
    console.warn("\nTESTING mergeWith add:", JSON.stringify(m1), JSON.stringify(m2))
    res = mergeWith((a,b) => a+b, m1, m2)
    console.warn("RES:", JSON.stringify(res))
    assert.deepEqual(res, { a: 10, b: 100, c: 0 })
    console.warn("SUCCESS")

    m1 = {a: {b: 3, c: 4}}
    m2 = {a: {b: 5}}
    console.warn("\nTESTING deepMerge:", JSON.stringify(m1), JSON.stringify(m2))
    res = deepMerge(m1, m2)
    console.warn("RES:", JSON.stringify(res))
    assert.deepEqual(res, { a: { b: 5, c: 4 } })
    console.warn("SUCCESS")

    //
    // Before and After Compare tests
    //
    const tests = [['tests/t1.yaml', 'tests/t1-result.yaml'],
                   ['tests/t2.yaml', 'tests/t2-result.yaml'],
                   ['tests/t3.yaml', 'tests/t3-result.yaml'],
                   ['tests/t4.yaml', 'tests/t4-result.yaml'],
                   ['tests/t5.yaml', 'tests/t5-result.yaml']]
    for (let [tPath, cPath] of tests) {
        loadTest(tPath, cPath)
    }
    break
  default:
    console.error(`Unknown mode ${mode}`)
    process.exit(1)
}

//// ^^^ Local testing only ^^^ ////
