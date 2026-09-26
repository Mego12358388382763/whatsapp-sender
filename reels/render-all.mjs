// Renders every reel to out/<id>.mp4.
// Run: npm run render            (all reels)
//      npm run render -- reel-03 (one reel)
import {execSync} from 'node:child_process';
import {reels} from './src/data/reels.ts';

const only = process.argv[2];
for (const r of reels.filter((x) => !only || x.id === only)) {
  console.log(`Rendering ${r.id}…`);
  execSync(`npx remotion render ${r.id} out/${r.id}.mp4`, {stdio: 'inherit'});
}
