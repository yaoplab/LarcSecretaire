-- Pré-remplissage des gabarits parents (10001-10800)
-- Style gabarit : enabled = FALSE, puis UPDATE à l'utilisation

INSERT INTO larcauth_aecuser (id, password, last_login, is_superuser,
    username, first_name, last_name, email, is_staff, is_active,
    date_joined, avatar, picture2, created, updated,
    type_parentutor, type_teacher, type_coordonator, type_supervisor,
    type_student, type_director, type_secretary, fk_gender_id)
SELECT s, '', NULL, FALSE,
    'parent.' || s, '', '', '', FALSE, FALSE,
    NOW(), '', '\x'::bytea, NOW(), NOW(),
    TRUE, FALSE, FALSE, FALSE,
    FALSE, FALSE, FALSE, NULL
FROM generate_series(10001, 10800) AS s
WHERE NOT EXISTS (SELECT 1 FROM larcauth_aecuser WHERE id = s);

INSERT INTO larcauth_parent (aecuser_ptr_id, enabled, nature)
SELECT s, FALSE, NULL
FROM generate_series(10001, 10800) AS s
WHERE NOT EXISTS (SELECT 1 FROM larcauth_parent WHERE aecuser_ptr_id = s);
