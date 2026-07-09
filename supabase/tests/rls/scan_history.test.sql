BEGIN;

CREATE EXTENSION IF NOT EXISTS pgtap;

SELECT plan(9);

-- Ensure RLS is enabled
SELECT ok(
    (
        SELECT relrowsecurity
        FROM pg_class
        WHERE oid = 'public.user_scan_history'::regclass
    ),
    'RLS enabled on user_scan_history'
);

-- --------------------------------------------------------------------
-- Create test users
-- --------------------------------------------------------------------

DELETE FROM public.user_scan_history
WHERE user_id IN (
    'aaaaaaaa-0000-4000-8000-000000000001',
    'bbbbbbbb-0000-4000-8000-000000000002'
);

DELETE FROM auth.users
WHERE id IN (
    'aaaaaaaa-0000-4000-8000-000000000001',
    'bbbbbbbb-0000-4000-8000-000000000002'
);

INSERT INTO auth.users (
    instance_id,
    id,
    aud,
    role,
    email,
    encrypted_password,
    email_confirmed_at,
    confirmation_token,
    recovery_token,
    email_change_token_new,
    email_change,
    raw_app_meta_data,
    raw_user_meta_data,
    created_at,
    updated_at
)
VALUES
(
    '00000000-0000-0000-0000-000000000000',
    'aaaaaaaa-0000-4000-8000-000000000001',
    'authenticated',
    'authenticated',
    'pgtap-user-a@test.local',
    '',
    now(),
    '',
    '',
    '',
    '',
    '{"provider":"email","providers":["email"]}',
    '{}',
    now(),
    now()
),
(
    '00000000-0000-0000-0000-000000000000',
    'bbbbbbbb-0000-4000-8000-000000000002',
    'authenticated',
    'authenticated',
    'pgtap-user-b@test.local',
    '',
    now(),
    '',
    '',
    '',
    '',
    '{"provider":"email","providers":["email"]}',
    '{}',
    now(),
    now()
);

-- --------------------------------------------------------------------
-- Seed rows
-- --------------------------------------------------------------------

INSERT INTO public.user_scan_history
(
    id,
    user_id,
    medicine_name,
    timestamp,
    scanned_at,
    query,
    source,
    status
)
VALUES
('row_a1','aaaaaaaa-0000-4000-8000-000000000001','Medicine A',0,now(),'q','scan','done'),
('row_a2','aaaaaaaa-0000-4000-8000-000000000001','Medicine A',0,now(),'q','scan','done'),
('row_a3','aaaaaaaa-0000-4000-8000-000000000001','Medicine A',0,now(),'q','scan','done'),
('row_b1','bbbbbbbb-0000-4000-8000-000000000002','Medicine B',0,now(),'q','scan','done'),
('row_b2','bbbbbbbb-0000-4000-8000-000000000002','Medicine B',0,now(),'q','scan','done'),
('row_b3','bbbbbbbb-0000-4000-8000-000000000002','Medicine B',0,now(),'q','scan','done');

-- --------------------------------------------------------------------
-- Login as user A
-- --------------------------------------------------------------------

SELECT set_config(
    'request.jwt.claims',
    json_build_object(
        'sub',
        'aaaaaaaa-0000-4000-8000-000000000001',
        'role',
        'authenticated'
    )::text,
    true
);

SET LOCAL ROLE authenticated;

-- --------------------------------------------------------------------
-- TEST 2
-- --------------------------------------------------------------------

SELECT is(
    (
        SELECT count(*)
        FROM public.user_scan_history
        WHERE id='row_a1'
    )::int,
    1,
    'Can read own row'
);

-- --------------------------------------------------------------------
-- TEST 3
-- --------------------------------------------------------------------

SELECT is(
    (
        SELECT count(*)
        FROM public.user_scan_history
        WHERE id='row_b1'
    )::int,
    0,
    'Cannot read other row'
);

-- --------------------------------------------------------------------
-- TEST 4
-- --------------------------------------------------------------------

SELECT lives_ok($$

INSERT INTO public.user_scan_history
(
    id,
    user_id,
    medicine_name,
    timestamp,
    scanned_at,
    query,
    source,
    status
)
VALUES
(
'row_new',
'aaaaaaaa-0000-4000-8000-000000000001',
'Medicine',
0,
now(),
'q',
'scan',
'done'
);

$$,'Insert own row');

-- --------------------------------------------------------------------
-- TEST 5
-- --------------------------------------------------------------------

SELECT throws_ok($$

INSERT INTO public.user_scan_history
(
    id,
    user_id,
    medicine_name,
    timestamp,
    scanned_at,
    query,
    source,
    status
)
VALUES
(
'row_hack',
'bbbbbbbb-0000-4000-8000-000000000002',
'Medicine',
0,
now(),
'q',
'scan',
'done'
);

$$,'42501');

-- --------------------------------------------------------------------
-- TEST 6
-- --------------------------------------------------------------------

WITH x AS (
    UPDATE public.user_scan_history
    SET medicine_name='Updated'
    WHERE id='row_a2'
    RETURNING id
)
SELECT is(
    (SELECT count(*) FROM x)::int,
    1,
    'Update own row'
);

-- --------------------------------------------------------------------
-- TEST 7
-- --------------------------------------------------------------------

WITH x AS (
    UPDATE public.user_scan_history
    SET medicine_name='Hack'
    WHERE id='row_b2'
    RETURNING id
)
SELECT is(
    (SELECT count(*) FROM x)::int,
    0,
    'Cannot update other row'
);

-- --------------------------------------------------------------------
-- TEST 8
-- --------------------------------------------------------------------

WITH x AS (
    DELETE FROM public.user_scan_history
    WHERE id='row_a3'
    RETURNING id
)
SELECT is(
    (SELECT count(*) FROM x)::int,
    1,
    'Delete own row'
);

-- --------------------------------------------------------------------
-- TEST 9
-- --------------------------------------------------------------------

WITH x AS (
    DELETE FROM public.user_scan_history
    WHERE id='row_b3'
    RETURNING id
)
SELECT is(
    (SELECT count(*) FROM x)::int,
    0,
    'Cannot delete other row'
);

SELECT * FROM finish();

ROLLBACK;