--
-- PostgreSQL database dump
--

\restrict zlNRryuVRkvNRNcJWutcgrZclXVBidi2Yrpbqsh79aS3f0YgpmBHQBFJLGmXZTX

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
-- Name: villas; Type: TABLE; Schema: public; Owner: postgres
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
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.villas OWNER TO postgres;

--
-- Name: villas_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.villas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.villas_id_seq OWNER TO postgres;

--
-- Name: villas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.villas_id_seq OWNED BY public.villas.id;


--
-- Name: visit_requests; Type: TABLE; Schema: public; Owner: postgres
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


ALTER TABLE public.visit_requests OWNER TO postgres;

--
-- Name: visit_requests_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.visit_requests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.visit_requests_id_seq OWNER TO postgres;

--
-- Name: visit_requests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.visit_requests_id_seq OWNED BY public.visit_requests.id;


--
-- Name: villas id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.villas ALTER COLUMN id SET DEFAULT nextval('public.villas_id_seq'::regclass);


--
-- Name: visit_requests id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.visit_requests ALTER COLUMN id SET DEFAULT nextval('public.visit_requests_id_seq'::regclass);


--
-- Data for Name: villas; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.villas (id, villa_code, city, area_type, price, land_size, building_size, bedrooms, master_bedrooms, is_townhouse, has_pool, has_jacuzzi, has_roof_garden, has_parking, has_storage, document_type, description, latitude, longitude, photos, video, status, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: visit_requests; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.visit_requests (id, villa_code, user_id, name, phone, area_type, request_type, status, created_at) FROM stdin;
\.


--
-- Name: villas_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.villas_id_seq', 1, false);


--
-- Name: visit_requests_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.visit_requests_id_seq', 1, false);


--
-- Name: villas villas_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.villas
    ADD CONSTRAINT villas_pkey PRIMARY KEY (id);


--
-- Name: villas villas_villa_code_unique; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.villas
    ADD CONSTRAINT villas_villa_code_unique UNIQUE (villa_code);


--
-- Name: visit_requests visit_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.visit_requests
    ADD CONSTRAINT visit_requests_pkey PRIMARY KEY (id);


--
-- PostgreSQL database dump complete
--

\unrestrict zlNRryuVRkvNRNcJWutcgrZclXVBidi2Yrpbqsh79aS3f0YgpmBHQBFJLGmXZTX

