# DCM run 2026-08-30-har0830-manual

**locksCertified: true**

This pack documents the **MANUAL researched card** delivered from the 08/30 PrizePicks HAR. It is **not** a hash-certified Python freeze (`COMPLETE_FROZEN`). Predictive claim: **NONE**.

## Capture
- HAR capture start: 2026-08-30T17:48:00.398Z (10:48 AM PT)
- HAR capture end: 2026-08-30T17:48:25.790Z
- Pack forecast_cutoff: 2026-08-30T17:48:00Z
- Eligible dump cutoff: 2026-08-30T17:48:25.790Z
- HAR sha256: `cd4c8c7c32427bcf5763ba88620a99c56c90c0a3b73cc67a7faf134cd42e7467`
- HAR was **not** copied into `audit/`
- Claims hashed with `dcm.research.claims.claim_record` (source_hash + claim_hash)
- Claim count: 27
- observed_at for all claims: 2026-08-30T17:47:00Z (<= cutoff)

## Why locksCertified is true
Coverage uses `dcm.research.coverage.evaluate_request`. Each of the 6 locks has:
- PLAYER status + role
- >=3 dict game_logs from basketball-reference **Last 5 Games** (all `GS=*`, i.e. starters)
- opportunity dict (teammate/opponent outs)
- efficiency dict (FG%/eFG%/TS% from the same B-R pages)
- EVENT scheduled_start / event_context
- MARKET_DEFINITION `definition_verified: true` for ast/pts/pra/reb

Those Last 5 tables are public box-score extracts, not fabricated logs. They are **not** a full role-epoch of every 2026 start. Shepard's 2026-08-09 log is a 5-minute start and is flagged in the claim.

This still is **not** a production Python freeze. `hashCertifiedPythonFreeze: false`.

## BEFORE
- board_rows 14607 → eligible 698 (WNBA 692 + CFB 6)
- research requests 782
- unique players 51 (WNBA 45 + CFB 6)
- skipped: goblin 2569, unsupported_sport 4992, live 601, side_unknown 1806, unsupported_market 2004, shadow 1936

## AFTER
6 STANDARD MORE locks (documented, not silently changed):

1. Jordin Canada ATL MORE ast 6.5
2. Kayla McBride MIN MORE pts 16.5
3. Allisha Gray ATL MORE pts 17.5
4. Nneka Ogwumike LAS MORE PRA 27.0
5. Jessica Shepard DAL MORE reb 10.5
6. Olivia Miles MIN MORE PRA 29.5

## Locks

### Jordin Canada ATL MORE ast 6.5 STANDARD
- event: MIN @ ATL (PrizePicks eventId 176427) vs MIN
- projectionId: 14265875
- complete: True
- missing: none
- notes: 7.4 APG cited (37 G) on B-R at research time; page snapshot 7.3 APG in 38 GS. Bonner out rest, Jones out leg.
- covering claim hashes (prefix): 88366a3d4cea…, bfeac689e972…, 17ecfada0a7c…, 8800e189fe77…, 93e58faee2fc…
- covering URLs:
  - https://api.prizepicks.com/projections?league_id=3&per_page=250&single_stat=true&in_game=true&state_code=CA&game_mode=prizepools
  - https://www.basketball-reference.com/wnba/players/c/canadjo01w.html
  - https://www.espn.com/wnba/preview/_/gameId/401857186
  - https://www.wnba.com/game/min-vs-atl-1022600297
### Kayla McBride MIN MORE pts 16.5 STANDARD
- event: MIN @ ATL (PrizePicks eventId 176427) vs ATL
- projectionId: 14265824
- complete: True
- missing: none
- notes: 18.1 PPG season (B-R / leaders); 17.8 L10 (ESPN preview 401857186).
- covering claim hashes (prefix): 88366a3d4cea…, bfeac689e972…, cb8da89fd454…, f52cdd692085…, 26afa8ea14b5…, 1e7409a06384…
- covering URLs:
  - https://api.prizepicks.com/projections?league_id=3&per_page=250&single_stat=true&in_game=true&state_code=CA&game_mode=prizepools
  - https://www.basketball-reference.com/wnba/players/m/mcbrika01w.html
  - https://www.basketball-reference.com/wnba/years/2026_leaders.html
  - https://www.espn.com/wnba/preview/_/gameId/401857186
  - https://www.wnba.com/game/min-vs-atl-1022600297
### Allisha Gray ATL MORE pts 17.5 STANDARD
- event: MIN @ ATL (PrizePicks eventId 176427) vs MIN
- projectionId: 14265870
- complete: True
- missing: none
- notes: 19.2 PPG in 39 games (B-R). Bonner/Jones out.
- covering claim hashes (prefix): 88366a3d4cea…, bfeac689e972…, cb8da89fd454…, 6812e4b209ad…
- covering URLs:
  - https://api.prizepicks.com/projections?league_id=3&per_page=250&single_stat=true&in_game=true&state_code=CA&game_mode=prizepools
  - https://www.basketball-reference.com/wnba/players/g/grayal01w.html
  - https://www.espn.com/wnba/preview/_/gameId/401857186
  - https://www.wnba.com/game/min-vs-atl-1022600297
### Nneka Ogwumike LAS MORE pra 27.0 STANDARD
- event: LAS @ SEA (PrizePicks eventId 176428) vs SEA
- projectionId: 14285634
- complete: True
- missing: none
- notes: Manual card 16.8/8.9/2.9 ≈ 28.6 PRA. Pack-time B-R 17.0/8.8/3.0 ≈ 28.8; ESPN game page 17.0/8.8.
- covering claim hashes (prefix): 24e7f019407e…, 2b8a09e5af38…, 9fdd29dec50c…, a4fba5022ea4…
- covering URLs:
  - https://api.prizepicks.com/projections?league_id=3&per_page=250&single_stat=true&in_game=true&state_code=CA&game_mode=prizepools
  - https://www.basketball-reference.com/wnba/players/o/ogwumnn01w.html
  - https://www.espn.com/wnba/game/_/gameId/401857187/sparks-storm
  - https://www.wnba.com/game/las-vs-sea-1022600298
### Jessica Shepard DAL MORE reb 10.5 STANDARD
- event: CON @ DAL (PrizePicks eventId 176430) vs CON
- projectionId: 14279482
- complete: True
- missing: none
- notes: 11.1 RPG (B-R). Griner OUT knee; Nelson-Ododa Q/GTD knee.
- covering claim hashes (prefix): 734fc2a52e89…, a23604b9d82c…, b45c2024244b…, e1fae8b670ce…
- covering URLs:
  - https://api.prizepicks.com/projections?league_id=3&per_page=250&single_stat=true&in_game=true&state_code=CA&game_mode=prizepools
  - https://www.basketball-reference.com/wnba/players/s/shepaje01w.html
  - https://www.espn.com/wnba/preview/_/gameId/401857189
### Olivia Miles MIN MORE pra 29.5 STANDARD
- event: MIN @ ATL (PrizePicks eventId 176427) vs ATL
- projectionId: 14265887
- complete: True
- missing: none
- notes: 19.7/4.6/6.1 ≈ 30.4 PRA in 37 starts (B-R).
- covering claim hashes (prefix): 88366a3d4cea…, bfeac689e972…, 9fdd29dec50c…, 12c883645169…
- covering URLs:
  - https://api.prizepicks.com/projections?league_id=3&per_page=250&single_stat=true&in_game=true&state_code=CA&game_mode=prizepools
  - https://www.basketball-reference.com/wnba/players/m/milesol01w.html
  - https://www.espn.com/wnba/preview/_/gameId/401857186
  - https://www.wnba.com/game/min-vs-atl-1022600297


## Do not bet
- **DeWanna Bonner** — OUT rest (ESPN MIN@ATL preview 401857186). ESPN injuries index at pack compile did **not** list Bonner; preview still does. Rejected.
- **Olivia Nelson-Ododa** — Q/GTD knee. ESPN injuries comment says questionable; status column says Out; CON@DAL preview lists out; game injury report GTD. Rejected either way.
- **Courtney Williams** — probable foot (ESPN injuries Aug 29). Preview says day-to-day (leg). Playable only if confirmed starting. Not a lock.
- **Brionna Jones** — OUT leg (ESPN injuries Aug 28). No eligible props.

## Traps
- **Veronica Burton MORE ast 11.5 DEMON** vs **5.8 APG** (B-R 2026 APG leaders rank 9).
- **Angel Reese MORE reb 15.5 DEMON** vs **12.5 RPG** (B-R 2026 RPG leader).

## WNBA slate 2026-08-30 (PT)
- MIN @ ATL 12:00 (3:00 PM ET) event 176427
- LAS @ SEA 14:00 (5:00 PM ET) event 176428
- GSV @ POR 16:00 (7:00 PM ET) event 176429
- CON @ DAL 17:30 (8:30 PM ET) event 176430

## Page-snapshot vs manual-card numbers
Do not silently change the 6 locks. Some live pages drifted vs the 10:48 PT citation:
- Canada APG: card **7.4 / 37 G**; B-R + ESPN preview snapshot **7.3 / 38 GP (38 GS)**
- Ogwumike PRA: card **16.8/8.9/2.9 = 28.6**; B-R snapshot **17.0/8.8/3.0 = 28.8**; ESPN LAS@SEA leaders **17.0/8.8**
Both numbers are stored on the PLAYER claims. Locks unchanged.

## URL verification
No primary URL 404'd.
- basketball-reference player pages + 2026_leaders.html: 200
- ESPN injuries + preview 401857186 + preview 401857189 + game 401857187: 200
- wnba.com min-vs-atl-1022600297 and las-vs-sea-1022600298: used in original research (transcript L334)
- PrizePicks projections URL: present in HAR; not re-fetched (session)

## Failures
None of the 6 locks missing ROLE_COMPARABLE_GAME_LOGS_MIN_3. Incomplete Python freeze / no Monte Carlo / no frozenForecastHash by design.
