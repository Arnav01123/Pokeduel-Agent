# PokéDuel Agent: Dragapult / Scizor / Tyranitar

A rule-based battle agent for the PokéDuel AI Gen 9 3v3 singles platform, plus a local arena that plays agents against each other on the real Pokémon Showdown battle engine.

> **Status: work in progress.** This is an incomplete, hand-written baseline, meant as the foundation for future ML-based agents. The arena already gives a learned model what it needs to train and be measured: a real battle engine, observations in the platform's format, and rule-based opponents to beat.

### What's still missing

- **No prediction.** The agent reacts to the board each turn; it doesn't read or predict the opponent.
- **Opposing items, moves and stats are invisible to it.** Threats are judged from the foe's types only, and "faster" means higher base Speed.
- **Rules cover named matchups only.** Anything outside them falls back to "most effective attack by type".
- **It's predictable.** A bot with tuned weights beats it every time in the mirror match (see Results).
- **Not yet tested on the live portal** or against human players.

## Team

Dragapult leads. Enter these sets on the portal; the agent can't see or change items, EVs or natures.

| Pokémon | Item | Ability | Nature | EVs | Moves |
| --- | --- | --- | --- | --- | --- |
| Dragapult | Choice Band | Clear Body | Hasty | 252 Atk / 4 SpD / 252 Spe | Dragon Darts, Flamethrower, U-turn, Phantom Force |
| Scizor | Metal Coat | Technician | Jolly | 252 Atk / 4 SpD / 252 Spe | Bullet Punch, Swords Dance, U-turn, Close Combat |
| Tyranitar | Focus Sash | Sand Stream | Impish | 252 HP / 252 Atk / 4 Def | Crunch, Rock Slide, Ice Punch, Earthquake |

Showdown export: [`agent/team.txt`](agent/team.txt).

## The agent

[`agent/pokeduel_agent.py`](agent/pokeduel_agent.py) is one file, standard library only. The platform calls `decide(observation)` each turn and gets back `move N`, `switch N` or `team NNN`.

Each Pokémon runs an ordered list of checks; the first match decides the turn:

- **Dragapult** attacks by type (Dragon Darts, Phantom Force on Ghost/Psychic, Flamethrower on Steel/Grass) and U-turns out of Fairy and Dark types. It remembers its Choice Band lock.
- **Scizor** hands Fire types to Tyranitar, U-turns out of Garchomp, Greninja, Gyarados and full-HP Venusaur, uses Close Combat on Tyranitar, sets one Swords Dance on Lapras and Snorlax, and finishes with priority Bullet Punch.
- **Tyranitar** leaves Lucario, trades with Garchomp using Focus Sash (survive Earthquake, KO with Ice Punch), and uses Rock Slide on Togekiss until it infers Aura Sphere.
- **Switch-ins** follow a matchup chain, including bringing Tyranitar in so sand finishes a foe at 20% HP or less.

Safety: HP values are normalised whatever scale the platform sends (percent, fraction or raw HP), every action is checked against the legal moves, and `decide()` never raises.

## Results

All games run on Pokémon Showdown's engine through [`arena/server.ts`](arena/server.ts), swapping sides every game. No agent sent an illegal action in any run.

**This agent vs the overnight heuristic bot** ([`baselines/overnight_v2.py`](baselines/overnight_v2.py)), 400 games each:

| Matchup | This agent | Overnight bot |
| --- | --- | --- |
| Each with its own team (Sash vs Assault Vest Tyranitar) | **347** | 53 |
| Both on the Focus Sash team | **233** | 167 |
| Both on the Assault Vest team | **251** | 149 |

**Against 600 random 3-Pokémon roster teams** (Showdown random-battle sets, piloted by a simple "strongest hit" bot): this agent wins 86.7%, the overnight bot 84.0%.

**Weight tuning.** [`baselines/overnight_v2_tuned.py`](baselines/overnight_v2_tuned.py) is the overnight bot with only its numeric weights changed (a random search plus local search, [`arena/search.py`](arena/search.py)) to beat this agent in the Focus Sash mirror. It won three fresh 200-game matches 200–0 each: both bots are deterministic, so this agent always plays the same line in the mirror and the tuned weights found the counter (one Swords Dance, then boosted priority Bullet Punch). The tuned weights generalise slightly worse: 80.7% against the random roster teams versus 82.3% with the original weights.

Caveats: this is Showdown's engine through a custom adapter, not the PokéDuel portal; Dragon Darts is presented to the agents as 100 base power (both hits); the random-team opponents are not the portal's own AI.

## Running the arena

Needs Python 3.10+, [Bun](https://bun.sh) and git.

```bash
cd arena
./setup.sh                 # clones Pokémon Showdown at a pinned commit
python3 run.py 400         # this agent vs the overnight bot, three team setups
python3 gauntlet.py 600    # both agents vs random roster teams
python3 search.py 120 6    # tune the overnight bot's weights against this agent
python3 validate.py        # check best_w.json on fresh seeds and random teams
```

## Layout

| Path | What it is |
| --- | --- |
| `agent/pokeduel_agent.py` | The agent to submit |
| `agent/team.txt` | Team in Showdown format |
| `baselines/overnight_v2.py` | Earlier heuristic bot, used as the opponent |
| `baselines/overnight_v2_tuned.py` | Same bot with weights tuned against this agent |
| `arena/server.ts` | Turns Showdown's battle state into PokéDuel-style observations |
| `arena/*.py` | Match runners, the weight search and validation |
