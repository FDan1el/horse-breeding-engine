-- =====================================================================
-- BREEDER TYCOON — ADATBÁZIS SÉMA
-- PostgreSQL 15+
-- =====================================================================
--
-- HÁROM RÉTEG:
--   1. PEDIGRÉ    — lassan változik, a lovak identitása és származása
--   2. VERSENY    — append-only eseménynapló
--   3. AGGREGÁTUM — íráskor frissül, olvasáskor csak lekérdezés
--
-- MÉRETEZÉS (a kapacitásmodellből, 20 000 aktív játékos):
--   aktív ló        ~214 000
--   kikerült ló     évente +~100 000 (halmozódik)
--   futam           ~2 959 / nap  =  ~1,1 M / év
--   eredménysor     ~32 500 / nap =  ~11,9 M / év
--
-- MIÉRT POSTGRES:
--   - a séma alapvetően relációs (származás, eredmények)
--   - a rejtett genetika viszont sémátlan → jsonb
--   - a jsonb GIN-indexelhető, ha valaha kell benne keresni
--   - tömb-típus (uuid[]) natív → az ős-tömb egy oszlop
--   - particionálás dátum szerint a versenytáblákra
--   - materializált nézet a ranglistákra

-- =====================================================================
-- 0. ALAPTÁBLA — FIÓK
-- =====================================================================
-- Ennek ELŐBB kell léteznie, mint a horse táblának, mert a
-- breeder_id és owner_id hivatkozik rá.

CREATE TABLE account (
    account_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name     text NOT NULL,
    balance          bigint NOT NULL DEFAULT 50000,
    seasons_played   integer NOT NULL DEFAULT 0,
    lifetime_earnings bigint NOT NULL DEFAULT 0,
    is_npc           boolean NOT NULL DEFAULT false,
    created_at       timestamptz NOT NULL DEFAULT now()
);


-- =====================================================================
-- 1. RÉTEG — PEDIGRÉ
-- =====================================================================

CREATE TYPE horse_sex     AS ENUM ('colt', 'filly');
CREATE TYPE horse_stage   AS ENUM ('foal','yearling','racer','breeding','pensioned','retired_out');
CREATE TYPE coat_colour   AS ENUM ('bay','chestnut','black','grey','palomino');
CREATE TYPE rarity_tier   AS ENUM ('common','uncommon','rare','special');
CREATE TYPE grade_letter  AS ENUM ('E','D','C','B-','B','B+','A-','A','A+');

CREATE TABLE horse (
    horse_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name            text NOT NULL UNIQUE,       -- névadási szabály: listing_sim.py
    sex             horse_sex NOT NULL,
    birth_season    integer NOT NULL,

    -- --- származás ---
    sire_id         uuid REFERENCES horse(horse_id),
    dam_id          uuid REFERENCES horse(horse_id),

    -- KÉT VONAL-AZONOSÍTÓ, SZIMMETRIKUSAN. Mindkettő SZÜLETÉSKOR
    -- öröklődik — így a vonal-lekérdezés indexelt keresés, nem rekurzió.
    family_id       uuid NOT NULL,   -- NŐI vonal, az ANYÁTÓL
    sire_line_id    uuid NOT NULL,   -- MÉN vonal, az APÁTÓL

    -- DENORMALIZÁLT ŐS-TÖMB: 4 generáció (2+4+8 = 14 hely).
    -- Redundáns, de a katalóguslap a leggyakoribb olvasási út, és
    -- az inbreeding így halmazmetszet lesz, nem fabejárás.
    ancestors       uuid[14],

    -- --- rejtett genetika: a játékos SOSEM látja ---
    genetics        jsonb NOT NULL,   -- a 10 tulajdonság valódi értéke (TGV)
    colour_genotype jsonb NOT NULL,   -- E/A/G/Cr lókusz

    -- --- látható, származtatott ---
    colour          coat_colour NOT NULL,
    born_colour     coat_colour NOT NULL,   -- a szürke színesen születik
    will_grey       boolean NOT NULL DEFAULT false,
    rarity          rarity_tier NOT NULL DEFAULT 'common',

    -- --- tulajdon ---
    -- A breeder_id SOHA nem változik, akkor sem, ha a ló gazdát cserél.
    -- Ez a tenyésztői prémium (15%) címzettje.
    breeder_id      uuid NOT NULL REFERENCES account(account_id),
    owner_id        uuid NOT NULL REFERENCES account(account_id),

    -- --- életciklus (lifecycle_sim.py) ---
    life_bar        numeric(5,2) NOT NULL DEFAULT 100,
    career_bar      numeric(5,2) NOT NULL DEFAULT 100,
    breeding_bar    numeric(5,2),           -- NULL a ménnél és a fiataloknál
    freshness       numeric(5,2) NOT NULL DEFAULT 100,
    stage           horse_stage NOT NULL DEFAULT 'foal',

    -- --- állapot ---
    injuries_total  integer NOT NULL DEFAULT 0,
    claimed_season  integer,                -- az igénylési zárolás miatt
    exited_season   integer,                -- amikor kikerült a játékból

    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_horse_sire        ON horse(sire_id) WHERE sire_id IS NOT NULL;
CREATE INDEX idx_horse_dam         ON horse(dam_id)  WHERE dam_id IS NOT NULL;
CREATE INDEX idx_horse_family      ON horse(family_id);
CREATE INDEX idx_horse_sire_line   ON horse(sire_line_id);
CREATE INDEX idx_horse_owner       ON horse(owner_id) WHERE stage <> 'retired_out';
CREATE INDEX idx_horse_breeder     ON horse(breeder_id);
CREATE INDEX idx_horse_stage       ON horse(stage);
-- az ős-tömbre GIN: "mely lovak pedigréjében szerepel X?"
CREATE INDEX idx_horse_ancestors   ON horse USING gin(ancestors);


-- Vonalak — a name-mező miatt megjeleníthető a katalóguslapon
CREATE TABLE bloodline (
    line_id     uuid PRIMARY KEY,
    line_type   text NOT NULL CHECK (line_type IN ('family','sire')),
    name        text NOT NULL,          -- pl. "Winvale-vonal"
    founder_id  uuid REFERENCES horse(horse_id),
    created_at  timestamptz NOT NULL DEFAULT now()
);


-- =====================================================================
-- 2. RÉTEG — VERSENY (append-only)
-- =====================================================================
-- Soha nem módosítunk, csak beszúrunk. Ez teszi auditálhatóvá
-- (csalásvédelem: integrity_sim.py) és visszajátszhatóvá.

CREATE TYPE track_surface AS ENUM ('dirt','turf','synthetic');
CREATE TYPE injury_level  AS ENUM ('minor','moderate','serious');

CREATE TABLE race (
    race_id      bigserial PRIMARY KEY,
    season       integer NOT NULL,
    day          smallint NOT NULL CHECK (day BETWEEN 1 AND 30),
    run_at       timestamptz NOT NULL,       -- a session tényleges ideje
    track_id     text NOT NULL,
    distance_f   smallint NOT NULL,
    surface      track_surface NOT NULL,
    going        text NOT NULL,
    bracket      text NOT NULL,              -- nyereménysáv
    classic_key  text,                       -- NULL, ha nem klasszikus
    is_black_type boolean NOT NULL DEFAULT false,
    purse        integer NOT NULL,
    field_size   smallint NOT NULL CHECK (field_size BETWEEN 8 AND 14)
) PARTITION BY RANGE (season);

-- Szezononkénti partíció: a régi szezonok hidegtárba tolhatók,
-- a lekérdezések többsége az aktuális szezont érinti.
CREATE TABLE race_s08 PARTITION OF race FOR VALUES FROM (8) TO (9);

CREATE INDEX idx_race_season_day ON race(season, day);
CREATE INDEX idx_race_track      ON race(track_id, run_at);


CREATE TABLE race_result (
    race_id     bigint NOT NULL,
    horse_id    uuid NOT NULL REFERENCES horse(horse_id),
    position    smallint NOT NULL,
    earnings    integer NOT NULL DEFAULT 0,
    jockey_id   uuid,
    trainer_id  uuid,
    injury      injury_level,
    -- a futás pillanatában érvényes állapot — a visszajátszhatóság miatt
    fill_bar    numeric(5,2),
    freshness   numeric(5,2),
    PRIMARY KEY (race_id, horse_id)
) PARTITION BY RANGE (race_id);

CREATE INDEX idx_result_horse ON race_result(horse_id, race_id DESC);


-- =====================================================================
-- 3. RÉTEG — AGGREGÁTUM
-- =====================================================================
-- Íráskor frissül, olvasáskor csak lekérdezés. EZ KÖTI ÖSSZE a két
-- adatbázist anélkül, hogy drága join-okat kellene futtatni.

CREATE TABLE horse_stats (
    horse_id            uuid PRIMARY KEY REFERENCES horse(horse_id),

    -- saját versenyzés
    starts              integer NOT NULL DEFAULT 0,
    wins                integer NOT NULL DEFAULT 0,
    places              integer NOT NULL DEFAULT 0,
    career_earnings     bigint  NOT NULL DEFAULT 0,
    black_type_wins     integer NOT NULL DEFAULT 0,
    black_type_places   integer NOT NULL DEFAULT 0,
    classic_wins        integer NOT NULL DEFAULT 0,
    best_bracket        text,

    -- SZÜLŐKÉNT — ezt a GYEREKEK futása frissíti
    progeny_count       integer NOT NULL DEFAULT 0,
    progeny_runners     integer NOT NULL DEFAULT 0,
    progeny_winners     integer NOT NULL DEFAULT 0,
    progeny_black_type  integer NOT NULL DEFAULT 0,
    progeny_classic     integer NOT NULL DEFAULT 0,
    progeny_earnings    bigint  NOT NULL DEFAULT 0,

    updated_at          timestamptz NOT NULL DEFAULT now()
);

-- Hall of Fame rangsorokhoz (lifecycle_sim.py)
CREATE INDEX idx_stats_racing_hof   ON horse_stats(career_earnings DESC, classic_wins DESC);
CREATE INDEX idx_stats_breeding_hof ON horse_stats(progeny_classic DESC, progeny_black_type DESC);


CREATE TABLE family_stats (
    family_id           uuid PRIMARY KEY,
    total_offspring     integer NOT NULL DEFAULT 0,
    runners             integer NOT NULL DEFAULT 0,
    winners             integer NOT NULL DEFAULT 0,
    black_type_count    integer NOT NULL DEFAULT 0,
    classic_count       integer NOT NULL DEFAULT 0,
    total_earnings      bigint  NOT NULL DEFAULT 0,
    family_grade        grade_letter NOT NULL DEFAULT 'E',
    -- a "Reines de Course" / blue hen megfelelője
    is_blue_hen_line    boolean NOT NULL DEFAULT false,
    updated_at          timestamptz NOT NULL DEFAULT now()
);


CREATE TABLE stud_stats (
    stud_id             uuid PRIMARY KEY REFERENCES horse(horse_id),
    seasons_at_stud     integer NOT NULL DEFAULT 0,
    mares_covered_total integer NOT NULL DEFAULT 0,
    mares_this_season   integer NOT NULL DEFAULT 0,   -- a 140-es könyv számlálója
    progeny_performance numeric(5,2),                 -- 0-100, a kereslet bemenete
    commercial_appeal   numeric(5,2),                 -- számított (stud_sim.py)
    globally_listed     boolean NOT NULL DEFAULT false,
    stud_fee            integer,
    is_open_policy      boolean NOT NULL DEFAULT false,
    updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_stud_listed ON stud_stats(globally_listed, commercial_appeal DESC)
    WHERE globally_listed;


-- =====================================================================
-- 4. AUKCIÓ ÉS TULAJDONVÁLTÁS
-- =====================================================================

CREATE TABLE auction_lot (
    lot_id          bigserial PRIMARY KEY,
    horse_id        uuid NOT NULL REFERENCES horse(horse_id),
    house_id        text NOT NULL,
    session_at      timestamptz NOT NULL,
    tier            text NOT NULL CHECK (tier IN ('elite','standard')),
    reserve         integer,
    hammer_price    integer,
    buyer_id        uuid REFERENCES account(account_id),
    seller_id       uuid NOT NULL REFERENCES account(account_id),
    result          text NOT NULL CHECK (result IN ('sold','unsold','npc_buyout','withdrawn')),
    bidders         smallint,
    -- a csalásvédelemhez (integrity_sim.py)
    npc_valuation   integer,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_lot_session ON auction_lot(session_at, house_id);
CREATE INDEX idx_lot_horse   ON auction_lot(horse_id);
-- kapcsolati gráf a csalásdetektáláshoz
CREATE INDEX idx_lot_pair    ON auction_lot(buyer_id, seller_id)
    WHERE result = 'sold';


CREATE TABLE ownership_history (
    horse_id    uuid NOT NULL REFERENCES horse(horse_id),
    from_owner  uuid,
    to_owner    uuid NOT NULL,
    season      integer NOT NULL,
    price       integer,
    channel     text NOT NULL,   -- 'auction' | 'quick_sale' | 'npc' | 'inheritance'
    changed_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (horse_id, changed_at)
);


-- =====================================================================
-- 5. TENYÉSZTÉS
-- =====================================================================

CREATE TABLE covering (
    covering_id     bigserial PRIMARY KEY,
    mare_id         uuid NOT NULL REFERENCES horse(horse_id),
    stud_id         uuid NOT NULL REFERENCES horse(horse_id),
    season          integer NOT NULL,
    fee_paid        integer NOT NULL,
    open_policy     boolean NOT NULL DEFAULT false,
    -- a szezononkénti egy csikó szabály érvényesítése
    conceived       boolean,
    foal_id         uuid REFERENCES horse(horse_id),
    -- amit a játékos ELŐRE látott
    inbreeding_shown numeric(5,4),
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (mare_id, season)      -- SZEZONONKÉNT EGY CSIKÓ
);

CREATE INDEX idx_covering_stud ON covering(stud_id, season);


-- =====================================================================
-- 6. INTEGRITÁS
-- =====================================================================
-- (az account tábla a 0. szekcióban, a horse előtt)


CREATE TABLE integrity_flag (
    flag_id      bigserial PRIMARY KEY,
    account_id   uuid NOT NULL REFERENCES account(account_id),
    counterparty uuid REFERENCES account(account_id),
    signal       text NOT NULL,   -- 'overpay' | 'repeat_pair' | 'passive_account'
    score        numeric(4,3) NOT NULL,
    level        text NOT NULL,   -- 'watch' | 'review' | 'action'
    detail       jsonb,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_flag_account ON integrity_flag(account_id, created_at DESC);


-- =====================================================================
-- 7. HALL OF FAME
-- =====================================================================

CREATE TABLE gallery_display (
    account_id   uuid NOT NULL REFERENCES account(account_id),
    gallery_type text NOT NULL CHECK (gallery_type IN ('breeding','racing')),
    horse_id     uuid NOT NULL REFERENCES horse(horse_id),
    slot         smallint NOT NULL,
    placed_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (account_id, gallery_type, slot)
);

-- A közös Hall of Fame két külön rangsora — materializált nézet,
-- mert ritkán változik és sokan olvassák.
CREATE MATERIALIZED VIEW hof_racing AS
SELECT h.horse_id, h.name, s.career_earnings, s.classic_wins,
       s.black_type_wins, s.wins,
       (s.career_earnings * 0.00035 + s.classic_wins * 25
        + s.black_type_wins * 8 + s.wins * 1.2) AS score
FROM horse h
JOIN horse_stats s USING (horse_id)
WHERE h.stage = 'retired_out'
ORDER BY score DESC
LIMIT 100;

CREATE MATERIALIZED VIEW hof_breeding AS
SELECT h.horse_id, h.name, s.progeny_classic, s.progeny_black_type,
       s.progeny_winners, s.progeny_earnings, s.progeny_count,
       (s.progeny_classic * 40 + s.progeny_black_type * 12
        + s.progeny_winners * 2 + s.progeny_earnings * 0.00008
        + s.progeny_count * 0.5) AS score
FROM horse h
JOIN horse_stats s USING (horse_id)
WHERE h.stage = 'retired_out'
ORDER BY score DESC
LIMIT 100;


-- =====================================================================
-- 8. A KÉT KRITIKUS LEKÉRDEZÉS
-- =====================================================================

-- (a) INBREEDING ELŐRE — amit a játékos a SAJÁT párosításánál lát.
--     Halmazmetszet a denormalizált ős-tömbön, rekurzió nélkül.
CREATE OR REPLACE FUNCTION preview_inbreeding(p_sire uuid, p_dam uuid)
RETURNS TABLE (shared_count int, coefficient numeric, shared_ids uuid[]) AS $$
    SELECT
        cardinality(shared)                              AS shared_count,
        LEAST(cardinality(shared) * 0.0625, 0.25)::numeric AS coefficient,
        shared                                            AS shared_ids
    FROM (
        SELECT ARRAY(
            SELECT unnest(s.ancestors)
            INTERSECT
            SELECT unnest(d.ancestors)
        ) AS shared
        FROM horse s, horse d
        WHERE s.horse_id = p_sire AND d.horse_id = p_dam
    ) x;
$$ LANGUAGE sql STABLE;


-- (b) KATALÓGUSLAP — három indexelt olvasás, join nélkül a
--     versenyadatbázisba.
CREATE OR REPLACE VIEW catalogue_page AS
SELECT
    h.horse_id, h.name, h.sex, h.colour, h.rarity, h.birth_season,
    h.ancestors,
    sire.name  AS sire_name,
    dam.name   AS dam_name,
    -- saját forma
    s.starts, s.wins, s.career_earnings, s.black_type_wins,
    -- utódok (ha tenyészállat)
    s.progeny_count, s.progeny_black_type, s.progeny_earnings,
    -- női család
    f.family_grade, f.black_type_count AS family_black_type,
    f.is_blue_hen_line
FROM horse h
LEFT JOIN horse sire ON sire.horse_id = h.sire_id
LEFT JOIN horse dam  ON dam.horse_id  = h.dam_id
LEFT JOIN horse_stats  s ON s.horse_id  = h.horse_id
LEFT JOIN family_stats f ON f.family_id = h.family_id;


-- =====================================================================
-- 9. AMI TUDATOSAN KIMARADT
-- =====================================================================
--
-- HIPOTETIKUS PÁROSÍTÁS-ELEMZŐ ("blank 4x pedigree"):
--   Az equineline.com kínál ilyet — üres pedigrébe beírt lovakkal
--   tesztelhető egy kereszteződés. Ez SZAKMAI KUTATÓESZKÖZ, nem
--   játékelem. A játékos a SAJÁT tervezett párosításánál látja előre
--   az inbreedinget (lásd 8/a), és ennyi.
--
-- NICKING-TÁBLA:
--   Ugyanez az ok. A sire_line_id megmarad a séma szimmetriája és a
--   vonal-megjelenítés miatt, de nem építünk rá kereszteződés-elemző
--   riportot.
--
-- DOSAGE (DP/DI/CD):
--   A valós adatbázisok sebesség/kitartás indexet számolnak a
--   pedigréből. Nálunk a távprofil (sprint/mile/middle/staying) már
--   közvetlenül tárolja ezt — nincs szükség származtatott indexre.
--
-- HERÉLÉS:
--   Nincs a játékban (lásd GDD 22.11).
