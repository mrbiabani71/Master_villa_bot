--
-- PostgreSQL database dump
--

\restrict x3ZzMwCuqQuE6FEQdMiLemW3lcuSvV0hYzbv65FovvQw57ndhhbkOnhlQRwudyC

-- Dumped from database version 16.10
-- Dumped by pg_dump version 16.10

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: villas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.villas (
    id integer NOT NULL,
    villa_code text NOT NULL,
    city text,
    area_type text,
    price real,
    land_size real,
    building_size real,
    bedrooms integer,
    master_bedrooms integer DEFAULT 0,
    is_townhouse integer DEFAULT 0 NOT NULL,
    has_pool integer DEFAULT 0 NOT NULL,
    has_jacuzzi integer DEFAULT 0 NOT NULL,
    has_roof_garden integer DEFAULT 0 NOT NULL,
    has_parking integer DEFAULT 0 NOT NULL,
    has_storage integer DEFAULT 0 NOT NULL,
    document_type text,
    description text,
    latitude real,
    longitude real,
    photos text,
    video text,
    status text DEFAULT 'draft'::text NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    telegram_message_id integer,
    telegram_media_group_id text,
    original_caption text,
    region text,
    villa_type text,
    facade text,
    utilities text,
    location_status text,
    community_status text
);


--
-- Name: villas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.villas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: villas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.villas_id_seq OWNED BY public.villas.id;


--
-- Name: visit_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.visit_requests (
    id integer NOT NULL,
    villa_code text NOT NULL,
    user_id integer NOT NULL,
    name text NOT NULL,
    phone text NOT NULL,
    area_type text DEFAULT ''::text,
    request_type text DEFAULT 'visit'::text,
    status text DEFAULT 'pending'::text,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: visit_requests_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.visit_requests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: visit_requests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.visit_requests_id_seq OWNED BY public.visit_requests.id;


--
-- Name: villas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.villas ALTER COLUMN id SET DEFAULT nextval('public.villas_id_seq'::regclass);


--
-- Name: visit_requests id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.visit_requests ALTER COLUMN id SET DEFAULT nextval('public.visit_requests_id_seq'::regclass);


--
-- Data for Name: villas; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.villas (id, villa_code, city, area_type, price, land_size, building_size, bedrooms, master_bedrooms, is_townhouse, has_pool, has_jacuzzi, has_roof_garden, has_parking, has_storage, document_type, description, latitude, longitude, photos, video, status, created_at, updated_at, telegram_message_id, telegram_media_group_id, original_caption, region, villa_type, facade, utilities, location_status, community_status) FROM stdin;
14	MV-1009	محمودآباد	ساحلی	7e+09	180	90	2	1	0	0	0	0	0	0	پروانه ساخت	شهرک حرفه ای با نگهبانی ۲۴ساعته\nجاده دریا\nمتریال ساخت عالی\nکولر و پکیج و رادیاتور\nحفاظ های درب و پنجره ریموتی\nپمپ و منبع آب و تسویه آب نصب\nتمام نصبیجات نو	\N	\N	AgACAgQAAyEFAAT5m73oAAICRWpR3yemxm9naGPY_TKaUYZvZ1E_AAI_D2sbmY5hUl21QDLqrZSJAQADAgADeQADPAQ	\N	published	2026-07-11 10:07:34.415669	2026-07-11 12:54:36.96	595	14270115608618004	محمودآباد \nجاده دریا \n۱۸۰متر زمین\n۹۰متر بنا \n۲ خواب ۱ خواب مستر\nانشعابات کنتور اختصاصی \n\nمتریال ساخت عالی \n پروانه ساخت \n شهرک حرفه ای با نگهبانی ۲۴ساعته \n\nکولر و پکیج و رادیاتور\n حفاظ های درب و پنجره ریموتی\nپمپ و منبع آب و تسویه آب نصب\n تمام نصبیجات نو \n\n قیمت  ۷ میلیارد	\N	\N	\N	انشعابات کنتور اختصاصی	\N	\N
15	MV-1010	محمودآباد	ساحلی	8.4999997e+09	220	130	2	1	0	0	0	0	0	0		شهرکی\nجاده دریا	\N	\N	AgACAgQAAyEFAAT5m73oAAICXWpSFgL7vVmDSe9EvNLooQLfH53XAALCDmsbQC5QUtGzZfwMjGd0AQADAgADeQADPAQ,AgACAgQAAyEFAAT5m73oAAICXmpSFgL9BofmQ1ZK6rI2lwABsWB2hwACww5rG0AuUFLgyv5A_cJ0fQEAAwIAA3kAAzwE,AgACAgQAAyEFAAT5m73oAAICX2pSFgIyk8UBl9LnP4RMJCffK7fsAALEDmsbQC5QUjwIPG3VvwSXAQADAgADeQADPAQ,AgACAgQAAyEFAAT5m73oAAICYGpSFgLYrQ4vdlR5g9-xFL3ciq5UAALFDmsbQC5QUmO3vVTm9mAWAQADAgADeQADPAQ,AgACAgQAAyEFAAT5m73oAAICYWpSFgLybjvUyjSfKmUepIyuoJUGAALGDmsbQC5QUsmLR7nEt4UmAQADAgADeQADPAQ,AgACAgQAAyEFAAT5m73oAAICYmpSFgJRQ0VGGNuGy1kYblmAiMD9AALHDmsbQC5QUnnDal0qb_j9AQADAgADeQADPAQ,AgACAgQAAyEFAAT5m73oAAICY2pSFgLwHOkAAZSHKZQ2jJ8bdJIczAACyA5rG0AuUFIrAAGjtGk5yacBAAMCAAN5AAM8BA,AgACAgQAAyEFAAT5m73oAAICZGpSFgIOq4gu64eAJdbwpe28wiBjAALJDmsbQC5QUnaz-VNCrchVAQADAgADeQADPAQ,AgACAgQAAyEFAAT5m73oAAICZWpSFgJ6_lxMuZSzilqqO8ShXPfJAALKDmsbQC5QUm966QbzlZkMAQADAgADeQADPAQ,AgACAgQAAyEFAAT5m73oAAICZmpSFgIqXt9T4ik8Wf0DzfzaxM7kAALLDmsbQC5QUviXP5HlE2RqAQADAgADeQADPAQ	\N	published	2026-07-11 10:08:06.164638	2026-07-11 10:08:06.164638	605	14270115863819220	محمودآباد \n جاده دریا \n ویلانیم پیلوت نمارومی\n220 زمین \n130 بنا \n 2خواب یک مستر \n انشعابات کنتور اختصاصی \nداخل بافت\n شهرکی\n \n\nقیمت  8.5 میلیارد	\N	\N	ویلانیم پیلوت نمارومی	انشعابات کنتور اختصاصی	\N	داخل بافت
16	MV-1011	محمودآباد	ساحلی	6.4999997e+09	150	80	2	1	0	0	0	0	0	0	پروانه ساختمان	شهرک با نگهبانی\nجاده کلوده	\N	\N	AgACAgQAAyEFAAT5m73oAAICZ2pSOSjEyBeX5jrZOTBvMV-SX_bZAAIaD2sbmY5hUpblRKRiygJoAQADAgADeQADPAQ,AgACAgQAAyEFAAT5m73oAAICaGpSOShOHT261yqu0BGq5Sujif1yAAIbD2sbmY5hUnV9dZ1KbMRyAQADAgADeQADPAQ,AgACAgQAAyEFAAT5m73oAAICaWpSOSh4suOu7CVcvSBYnrJpKgUmAAIgD2sbmY5hUi_CCtMoN35hAQADAgADeQADPAQ,AgACAgQAAyEFAAT5m73oAAICampSOSj6x2Cin44EW45T_fRdPsGuAAIiD2sbmY5hUjRFTfjIkCh3AQADAgADeQADPAQ,AgACAgQAAyEFAAT5m73oAAICa2pSOShhWR8BMY2ex6nC5tIw5rvyAAIhD2sbmY5hUgcM8Mm1symBAQADAgADeQADPAQ,AgACAgQAAyEFAAT5m73oAAICbGpSOShm9CESqCLtnedEHeNItjxrAAIdD2sbmY5hUkwyjY03xV8YAQADAgADeQADPAQ,AgACAgQAAyEFAAT5m73oAAICbWpSOSjtSXLpt1yzRu7v9xj6cEDaAAIcD2sbmY5hUprJAAH8pe22jgEAAwIAA3kAAzwE,AgACAgQAAyEFAAT5m73oAAICbmpSOSgBoggm8IMAAd3DYOo8LSUR-AACHg9rG5mOYVIG_2tB6ZL2ogEAAwIAA3kAAzwE,AgACAgQAAyEFAAT5m73oAAICb2pSOSjXS8OYoFPPsJZH0glU6vRnAAIjD2sbmY5hUoxDf3ehK-HhAQADAgADeQADPAQ,AgACAgQAAyEFAAT5m73oAAICcGpSOSg4IHrdqI0wGLNWHVvQE7xBAAIfD2sbmY5hUjbW5wpVz1_pAQADAgADeQADPAQ	\N	published	2026-07-11 12:38:03.519233	2026-07-11 12:38:03.519233	615	14270187842307260	محمودآباد \nجاده کلوده  \nزمین ۱۵۰\n بنا ۸۰ \nدو خواب یک مستر \nپروانه ساختمان \nانشعابات اختصاصی تحویل \nشهرک با نگهبانی \nقیمت 6.5 میلیارد	\N	\N	\N	انشعابات اختصاصی تحویل	\N	\N
13	MV-1008	محمودآباد	ساحلی	1e+10	300	130	2	1	0	1	0	0	0	0	پروانه ساخت و پایان کار، سند تک برگ	جاده دریا\n۱۳۰ متر بنا\n۳کنتور به صورت اختصاصی\nکوچه ۸متری\nمستقل محیط غیر بومی	\N	\N	AgACAgQAAyEFAAT5m73oAAICT2pR34DMBx3cYeApKdx78xGIURaFAAJaD2sb6A3gUKM8KN9Rmr2yAQADAgADeAADPAQ	\N	published	2026-07-11 06:15:49.668034	2026-07-11 06:15:49.668034	\N	\N	\N	\N	\N	\N	\N	\N	\N
\.


--
-- Data for Name: visit_requests; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.visit_requests (id, villa_code, user_id, name, phone, area_type, request_type, status, created_at) FROM stdin;
\.


--
-- Name: villas_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.villas_id_seq', 16, true);


--
-- Name: visit_requests_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.visit_requests_id_seq', 1, false);


--
-- Name: villas villas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.villas
    ADD CONSTRAINT villas_pkey PRIMARY KEY (id);


--
-- Name: villas villas_villa_code_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.villas
    ADD CONSTRAINT villas_villa_code_unique UNIQUE (villa_code);


--
-- Name: visit_requests visit_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.visit_requests
    ADD CONSTRAINT visit_requests_pkey PRIMARY KEY (id);


--
-- Name: villas_telegram_message_id_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX villas_telegram_message_id_unique ON public.villas USING btree (telegram_message_id) WHERE (telegram_message_id IS NOT NULL);


--
-- PostgreSQL database dump complete
--

\unrestrict x3ZzMwCuqQuE6FEQdMiLemW3lcuSvV0hYzbv65FovvQw57ndhhbkOnhlQRwudyC

