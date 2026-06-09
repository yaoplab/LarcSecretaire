-- ============================================================
-- student_event : Table centralisée de présence / événements
-- ============================================================
-- Principes :
--   - INSERT only (traces temporelles)
--   - Tous profils (SUPERVISEUR, COORD, ADMIN) écrivent dans
--     la même table
--   - agenda_day_id auto-résolu via trigger depuis event_at
-- ============================================================

-- 1. Colonne day_notice pour les jours particuliers
ALTER TABLE public.larcauth_agenda
    ADD COLUMN IF NOT EXISTS day_notice TEXT;

COMMENT ON COLUMN public.larcauth_agenda.day_notice IS
    'Avis superviseur pour un jour particulier (événement, congé spécial, etc.)';

-- 2. Table événements
CREATE TABLE IF NOT EXISTS student_event (
    event_id       INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    student_id     INTEGER NOT NULL REFERENCES larcauth_student(aecuser_ptr_id)
                             ON DELETE CASCADE,
    agenda_day_id  INTEGER NOT NULL REFERENCES larcauth_agenda(id),
    event_type     TEXT NOT NULL
                     CHECK (event_type IN (
                       'arrival', 'departure', 'exit',
                       'return', 'absence', 'justified', 'late'
                     )),
    event_at       TIMESTAMP NOT NULL,
    note           TEXT CHECK (length(note) <= 200),
    source         TEXT NOT NULL DEFAULT 'intranet'
                     CHECK (source IN ('intranet', 'cloud')),
    created_by     INTEGER NOT NULL REFERENCES larcauth_aecuser(id),
    validated_by   INTEGER REFERENCES larcauth_aecuser(id),
    validated      BOOLEAN NOT NULL DEFAULT FALSE,
    validated_at   TIMESTAMP,
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sync_revision  BIGINT DEFAULT 0,
    synced         BOOLEAN DEFAULT FALSE
);

-- 3. Index
CREATE INDEX IF NOT EXISTS idx_event_student_date
    ON student_event(student_id, event_at);

CREATE INDEX IF NOT EXISTS idx_event_date
    ON student_event(event_at);

CREATE INDEX IF NOT EXISTS idx_event_agenda_day
    ON student_event(agenda_day_id);

CREATE INDEX IF NOT EXISTS idx_event_type
    ON student_event(event_type);

CREATE INDEX IF NOT EXISTS idx_event_validated
    ON student_event(validated_by) WHERE validated_by IS NULL;

-- 4. Trigger auto-résolution agenda_day_id
CREATE OR REPLACE FUNCTION resolve_agenda_day()
RETURNS TRIGGER AS $$
BEGIN
    SELECT id INTO NEW.agenda_day_id
    FROM larcauth_agenda
    WHERE date_all = DATE(NEW.event_at);
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Aucun jour agenda trouvé pour le %', DATE(NEW.event_at);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_resolve_agenda_day ON student_event;
CREATE TRIGGER trg_resolve_agenda_day
    BEFORE INSERT ON student_event
    FOR EACH ROW EXECUTE FUNCTION resolve_agenda_day();

-- 5. Vues de synthèse
-- Présence résumée par élève × jour
CREATE OR REPLACE VIEW student_daily_summary AS
SELECT
    se.student_id,
    ag.date_all AS day,
    ag.working_day,
    ag.day_notice,
    CASE
        WHEN EXISTS (
            SELECT 1 FROM student_event e2
            WHERE e2.student_id = se.student_id
              AND e2.agenda_day_id = ag.id
              AND e2.event_type = 'absence'
              AND e2.validated_by IS NULL
        ) THEN 'ABSENT'
        WHEN EXISTS (
            SELECT 1 FROM student_event e3
            WHERE e3.student_id = se.student_id
              AND e3.agenda_day_id = ag.id
              AND e3.event_type != 'absence'
        ) THEN 'PRESENT'
        ELSE 'UNKNOWN'
    END AS presence,
    MIN(CASE WHEN se.event_type = 'arrival'   THEN se.event_at END) AS first_arrival,
    MAX(CASE WHEN se.event_type = 'departure' THEN se.event_at END) AS last_departure,
    COUNT(*) FILTER (WHERE se.event_type = 'exit')      AS exit_count,
    COUNT(*) FILTER (WHERE se.event_type = 'late')      AS late_count,
    COUNT(*) FILTER (WHERE se.event_type = 'absence'
        AND se.validated_by IS NULL) AS absence_count,
    COUNT(*) FILTER (WHERE se.event_type = 'justified') AS justified_count,
    COUNT(*) AS total_events
FROM student_event se
JOIN larcauth_agenda ag ON ag.id = se.agenda_day_id
GROUP BY se.student_id, ag.id, ag.date_all, ag.working_day, ag.day_notice;

-- Alertes : 3+ sorties ou absence non justifiée (7 derniers jours)
CREATE OR REPLACE VIEW student_alerts AS
SELECT
    se.student_id,
    aec.last_name || ' ' || aec.first_name AS student_name,
    ag.date_all AS day,
    ag.working_day,
    ag.day_notice,
    COUNT(*) FILTER (WHERE se.event_type = 'exit') AS exit_count,
    CASE
        WHEN COUNT(*) FILTER (WHERE se.event_type = 'absence'
            AND se.validated_by IS NULL) > 0 THEN TRUE
        ELSE FALSE
    END AS has_unjustified_absence,
    MAX(se.event_at) AS last_event
FROM student_event se
JOIN larcauth_agenda ag ON ag.id = se.agenda_day_id
JOIN larcauth_student s ON s.aecuser_ptr_id = se.student_id
JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
WHERE se.event_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY se.student_id, aec.last_name, aec.first_name,
         ag.id, ag.date_all, ag.working_day, ag.day_notice
HAVING
    COUNT(*) FILTER (WHERE se.event_type = 'exit') >= 3
    OR COUNT(*) FILTER (WHERE se.event_type = 'absence'
        AND se.validated_by IS NULL) > 0
ORDER BY has_unjustified_absence DESC, exit_count DESC;
