import {Battle, Dex, Teams} from './ps/sim';
import * as readline from 'readline';
let battle: any = null;
const out = (o: any) => process.stdout.write(JSON.stringify(o) + '\n');
function pct(p: any) { return p.maxhp ? Math.round(p.hp / p.maxhp * 1000) / 10 : 0; }
function mult(type: string, types: string[]) {
  if (!Dex.getImmunity(type, types)) return 0;
  return Math.pow(2, Dex.getEffectiveness(type, types));
}
function obsFor(s: any) {
  const req = s.activeRequest;
  if (!req || req.wait) return null;
  const my_team = s.pokemon.map((p: any, i: number) => ({name: p.species.name, hp_percent: pct(p), active: i === 0 && !req.teamPreview, fainted: p.fainted}));
  if (req.teamPreview) return {turn: 0, team_preview: true, force_switch: false, my_team, valid_moves: [], valid_switches: []};
  const me = s.active[0], foe = s.foe.active[0];
  const foeTypes = foe.getTypes();
  const a = req.active && req.active[0];
  let valid_moves: any[] = [];
  if (!req.forceSwitch && a) {
    a.moves.forEach((m: any, i: number) => {
      if (m.disabled) return;
      const mv = Dex.moves.get(m.id);
      let bp = mv.basePower; if (mv.id === 'dragondarts') bp = 100;
      valid_moves.push({index: i + 1, id: mv.id, name: mv.name, type: mv.type, category: mv.category, base_power: bp,
        accuracy: mv.accuracy === true ? 100 : mv.accuracy, type_multiplier: mult(mv.type, foeTypes), stab: me.getTypes().includes(mv.type)});
    });
  }
  let valid_switches: any[] = [];
  if (req.forceSwitch || !(a && (a.trapped || a.maybeTrapped))) {
    s.pokemon.forEach((p: any, i: number) => {
      if (i === 0 || p.fainted) return;
      valid_switches.push({index: i + 1, name: p.species.name, types: p.getTypes(), hp_percent: pct(p), active: false, fainted: false});
    });
  }
  return {turn: battle.turn, team_preview: false, force_switch: !!req.forceSwitch,
    my_active: {name: me.species.name, types: me.getTypes(), hp_percent: pct(me), boosts: {...me.boosts}, condition: `${me.hp}/${me.maxhp}`},
    foe: {name: foe.species.name, types: foeTypes, hp_percent: pct(foe)},
    my_team, valid_moves, valid_switches, weather: battle.field.weather || ''};
}
function state() {
  return {ended: battle.ended, winner: battle.winner, turn: battle.turn,
    obs: {p1: battle.ended ? null : obsFor(battle.sides[0]), p2: battle.ended ? null : obsFor(battle.sides[1])}};
}
const rl = readline.createInterface({input: process.stdin});
rl.on('line', (line) => {
  const c = JSON.parse(line);
  try {
    if (c.cmd === 'new') {
      battle = new Battle({formatid: 'gen9customgame' as any, seed: c.seed});
      battle.setPlayer('p1', {name: 'A', team: Teams.import(c.p1team)});
      battle.setPlayer('p2', {name: 'B', team: Teams.import(c.p2team)});
      out(state());
    } else if (c.cmd === 'choose') {
      const bad: any = {};
      for (const sid of ['p1', 'p2']) {
        if (c[sid] == null) continue;
        const side = battle.getSide(sid);
        let ok = false;
        try { ok = battle.choose(sid, c[sid]); } catch (e) { ok = false; }
        if (!ok) { bad[sid] = c[sid]; side.clearChoice(); battle.choose(sid, 'default'); }
      }
      const st: any = state(); st.bad = bad;
      if (battle.turn > 300) { st.ended = true; st.winner = 'TIMEOUT'; }
      out(st);
    }
  } catch (e: any) { out({error: String(e && e.stack || e)}); }
});
