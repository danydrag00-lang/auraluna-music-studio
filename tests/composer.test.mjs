import test from 'node:test';import assert from 'node:assert/strict';import {compose,fingerprint} from '../src/composer.mjs';
test('seed reproducibility and diversity',()=>{const a=compose({seed:1}),b=compose({seed:1}),c=compose({seed:2});assert.deepEqual(a,b);assert.notEqual(fingerprint(a),fingerprint(c));});
test('bounded note events',()=>{for(const mood of ['sleep','spa','zen','indian','focus']){const p=compose({seed:42,mood,seconds:30,instruments:['piano','flute']});assert.ok(p.events.length);for(const e of p.events){assert.ok(e.time>=0&&e.duration>0&&e.time+e.duration<=30+1e-9);assert.ok(e.pitch>=0&&e.pitch<=127)}}});
test('reject missing instruments and invalid durations',()=>{assert.throws(()=>compose({seed:1,instruments:[]}));assert.throws(()=>compose({seed:1,seconds:3600}));});
