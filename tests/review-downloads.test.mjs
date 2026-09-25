import test from 'node:test';
import assert from 'node:assert/strict';
import {addDownloadLibrary} from '../netlify/lib/review-downloads.mjs';

test('download library includes current linked media, posters and captions only',()=>{
 const manifest={files:{'movie.mp4':{size:1200000000},'cover.png':{size:2000000},'captions.vtt':{size:300},'old.mp4':{size:10}}};
 const body='<main><video poster="/review/demo/files/cover.png"><source src="/review/demo/files/movie.mp4"><track src="/review/demo/files/captions.vtt"></video><a href="/review/demo/files/movie.mp4">View</a><a href="https://example.com/article">Article</a></main>';
 const rendered=addDownloadLibrary(body,'demo',manifest);
 assert.match(rendered,/All 3 files/);assert.match(rendered,/movie.mp4\?download=1/);assert.match(rendered,/1.20 GB/);
 assert.ok(!rendered.includes('old.mp4'));assert.match(rendered,/href="https:\/\/example.com\/article"/);
});
test('unlisted or foreign-room references never become download entries',()=>{
 const body='<main><a href="/review/other/files/movie.mp4">Other</a><a href="/review/demo/files/missing.mp4">Missing</a></main>';
 assert.equal(addDownloadLibrary(body,'demo',{files:{'movie.mp4':{size:1}}}),body);
});
test('download library escapes labels and handles encoded paths',()=>{
 const body='<main><a href="/review/demo/files/notes%20%26%20links.md?download=1">Notes</a></main>';
 const result=addDownloadLibrary(body,'demo',{files:{'notes & links.md':{size:10}}});
 assert.match(result,/All 1 files/);assert.match(result,/notes &amp; links.md/);
});
