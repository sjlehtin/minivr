-- Hae kaikki asemat joille on suora yhteys lähtöasemalta (tässä id=0)
--
-- Huom! Suunta voi olla väärä ja yhteyden toteutuminen pitää tarkistaa erikseen

SELECT DISTINCT station.name
  FROM minivr_stop stop, minivr_station station
 WHERE station.id = stop.station_id
       AND stop.service_id IN
           (SELECT service.id
              FROM minivr_service service, minivr_stop stop
             WHERE service.id = stop.service_id
                   AND stop.station_id = 0)
 ORDER BY name;

-- Hae kaikki asematunnukset jolle pääsee suoralla yhteydellä lähtöasemalta (tässä id=0)

SELECT DISTINCT stop.station_id
  FROM minivr_stop stop
 WHERE stop.service_id IN
       (SELECT service.id
          FROM minivr_service service, minivr_stop stop
         WHERE stop.departure_time IS NOT NULL
               AND service.id=stop.service_id
               AND stop.station_id=0)

-- Hae kaikki junavuorot jotka lähtevät tai saapuvat asemalle (tässä id=0)

SELECT DISTINCT service.id
  FROM minivr_service service, minivr_stop stop
 WHERE stop.station_id = 0
       AND service.id=stop.service_id

-- Hae kaikki junavuorot joihin on yhteys yhdellä vaihdolla lähtöasemalta (tässä id=0)

SELECT stop.service_id
  FROM minivr_stop stop
 WHERE stop.id IN
    (SELECT stop.id
      FROM minivr_stop stop
     WHERE stop.service_id IN
        (SELECT service.id
          FROM minivr_service service, minivr_stop stop
         WHERE stop.station_id = 0
               AND service.id=stop.service_id))


SELECT DISTINCT station_id, service_id
  FROM minivr_stop where service_id IN
       (SELECT service.id, stop.station_id
          FROM minivr_service service, minivr_stop stop
         WHERE service.id=stop.service_id);

CREATE VIEW minivr_station_service
            (service_id, station_id)
         AS
   SELECT service.id, stop.station_id
      FROM minivr_service service, minivr_stop stop
     WHERE service.id=stop.service_id;

-- Find all service combinations in database without regarding date/time
-- restrictions or change times
--
-- NOTE: In real life these are Way too big without additional contrains, like
-- dates or such. So please try something like
-- 
-- SELECT *
--   FROM minivr_one_change_service
--  WHERE s1_id = ? AND s3_id = ? (+ future date restrictions)

CREATE OR REPLACE VIEW minivr_no_change_service
            (s1_id, s2_id, service_id)
         AS
    SELECT s1.station_id, s2.station_id, s1.service_id
      FROM minivr_station_service s1, minivr_station_service s2
     WHERE s1.service_id = s2.service_id
       AND s1.station_id <> s2.station_id;

CREATE OR REPLACE VIEW minivr_one_change_service
            (s1_id, s2_id, s3_id, service1_id, service2_id)
        AS
    SELECT s1.s1_id, s1.s2_id, s2.s2_id, s1.service_id, s2.service_id
      FROM minivr_no_change_service s1, minivr_station_station_service s2
     WHERE s1.s2_id = s2.s1_id
       AND s1.s1_id <> s2.s2_id
       AND s1.service_id <> s2.service_id;

CREATE OR REPLACE VIEW minivr_two_change_service
            (s1_id, s2_id, s3_id, s4_id, service1_id, service2_id, service3_id)
        AS
    SELECT s1.s1_id, s2.s1_id, s2.s2_id, s2.s3_id, s1.service_id, s2.service1_id, s2.service2_id
      FROM minivr_no_change_service s1,
           minivr_one_change_service s2
     WHERE s1.s2_id = s2.s1_id
       AND s1.s1_id <> s2.s3_id
       AND s1.service_id <> s2.service1_id
       AND s1.service_id <> s2.service2_id;
    -- I'm not sure whether this last comparison actually prevents finding some good routes.
    -- It certainly isn't right in the general case, but might be a practical
    -- optimisation on railways.


-- Hae kaikki asemat joihin on yhteys yhdellä vaihdolla lähtöasemalta (tässä id=0)

SELECT stop.station_id
  FROM minivr_stop stop
 WHERE stop.service_id IN
       (SELECT stop.service_id
          FROM minivr_stop stop
         WHERE stop.id IN
            (SELECT stop.id
              FROM minivr_stop stop
             WHERE stop.service_id IN
                (SELECT service.id
                  FROM minivr_service service, minivr_stop stop
                 WHERE stop.station_id = 0
                       AND service.id=stop.service_id))

-- Hae kaikki asemat joihin on yhteys yhdellä vaihdolla lähtöasemalta (tässä id=0)

-- PS. Ei toimi :(
SELECT DISTINCT station.name
  FROM minivr_stop stop,
       minivr_station station
 WHERE station.id = stop.station_id
       AND stop.id IN
    (SELECT stop.id
      FROM minivr_stop stop
     WHERE stop.service_id IN
        (SELECT service.id
          FROM minivr_service service, minivr_stop stop
         WHERE stop.station_id = 0
               AND service.id=stop.service_id))


-- Hae kaikki asemat jolle pääsee suoralla yhteydellä lähtöasemalta (tässä id=0)

SELECT DISTINCT station.name
  FROM minivr_stop stop, minivr_station station
 WHERE station.id = stop.station_id
       AND stop.service_id IN
           (SELECT service.id
              FROM minivr_service service, minivr_stop stop
             WHERE stop.station_id = 0
                   AND stop.departure_time IS NOT NULL
                   AND service.id=stop.service_id)
 ORDER BY name;


-- "Monsteri"

SELECT * FROM
  (SELECT
     (60 * extract(hour   from minivr_service.departure_time)
       +   extract(minute from minivr_service.departure_time)
       + minivr_stop.departure_time
       - %%s)
     AS t,
     minivr_stop.*
     FROM minivr_stop
         INNER JOIN minivr_service
                 ON (minivr_stop.service_id = minivr_service.id)
         INNER JOIN minivr_station
                 ON (minivr_stop.station_id = minivr_station.id)
     WHERE UPPER(minivr_station.name::text) = UPPER(%%s)
       AND minivr_service.free_seats > 0

--       FIXME: this doesnt take into account the fact that the
--       time may wrap into another date. Thats not as trivial to
--       handle as it may seem.
       AND (minivr_stop.year_min IS NULL
            OR (    minivr_stop.year_min <= %%s
                AND minivr_stop.year_max >= %%s
                AND minivr_stop.month_min <= %%s
                AND minivr_stop.month_max >= %%s
                AND minivr_stop.weekday_min <= %%s
                AND minivr_stop.weekday_max >= %%s))
       AND minivr_stop.departure_time IS NOT NULL)
  AS ts

--         params = [wanted_time, from_station_name, wanted_year, wanted_year,
--         wanted_month, wanted_month, wanted_weekday, wanted_weekday]

-- "Monsteri" pilkottuna

CREATE OR REPLACE VIEW all_dates
            (d, year, month, day, dow)
         AS
     SELECT to_date(year||'-'||month||'-'||day, 'YYYY-MM-DD'), year, month, day, ((EXTRACT(DOW FROM to_date(year||'-'||month||'-'||day, 'YYYY-MM-DD'))::integer + 6) % 7) + 1
       FROM unnest(array[1,2,3,4,5,6,7,8,9,10,11,12]) month,
            unnest(array[2010,2011,2012]) year,
            unnest(array[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31]) day;

CREATE OR REPLACE VIEW minivr_available_service_by_date
            (station_id, service_id, arrival_time, departure_time)
         AS
    SELECT d.d, stop.station_id, stop.service_id,
           d.d::timestamptz + stop.arrival_time * '1 minute'::interval,
           d.d::timestamptz + stop.departure_time * '1 minute'::interval
      FROM all_dates d,
           minivr_stop stop
     WHERE stop.year_min IS NULL
            OR (d.year BETWEEN stop.year_min AND stop.year_max
                AND d.month BETWEEN stop.month_min AND stop.month_max
                AND d.dow BETWEEN stop.weekday_min AND stop.weekday_max);

SELECT service.departure_time 
