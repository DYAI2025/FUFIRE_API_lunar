#### Schemas

BaziDates

Expand all**object**

BaziPillars

Expand all**object**

BaziRequest

Expand all**object**

BaziSection

Expand all**object**

ChartRequest

Expand all**object**

ChartResponse

Collapse all**object**

engine_version

Collapse all**string**

Engine build version

parameter_set_id

Collapse all**string**

Parameter set identifier

time_scales

Collapse all**object**

utc

Collapse all**string**

UTC datetime ISO 8601

civil_local

Collapse all**string**

Civil local datetime ISO 8601 with offset

jd_ut

Collapse all**number**

Julian Day (UT)

tlst_hours

Collapse all**number**

True Local Solar Time in decimal hours

eot_min

Collapse all**number**

Equation of Time in minutes

dst_status

Collapse all**string**

DST resolution status: 'ok', 'shifted', etc.

dst_fold

Collapse all**integer**

DST fold value (0 or 1)

tz_abbrev

Collapse all**string**

Timezone abbreviation (e.g. CEST, CET)

quality

Collapse all**object**

tlst

Collapse all**string**

True Local Solar Time quality: 'ok' or diagnostic

positions

Collapse all**array<object>**

Western planetary positions

Items

Collapse all**object**

name

Collapse all**string**

Body name (Sun, Moon, Mercury, ...)

longitude_deg

Collapse all**(number | null)**

Ecliptic longitude 0-360°

Any of

Collapse all**(number | null)**

#0

**number**

#1

**null**

latitude_deg

Collapse all**(number | null)**

Ecliptic latitude in degrees

Any of

Collapse all**(number | null)**

#0

**number**

#1

**null**

speed_deg_per_day

Collapse all**(number | null)**

Daily speed in degrees

Any of

Collapse all**(number | null)**

#0

**number**

#1

**null**

distance_au

Collapse all**(number | null)**

Distance in AU

Any of

Collapse all**(number | null)**

#0

**number**

#1

**null**

is_retrograde

Collapse all**boolean**

True if body is retrograde

Defaultfalse

sign_index

Collapse all**integer**

Zodiac sign index 0-11 (Aries=0)

sign_name

Collapse all**string**

English zodiac sign name

sign_name_de

Collapse all**string**

German zodiac sign name

degree_in_sign

Collapse all**(number | null)**

Degree within the sign 0-30°

Any of

Collapse all**(number | null)**

#0

**number**

#1

**null**

bazi

Collapse all**object**

Four Pillars of Destiny

ruleset_id

Collapse all**string**

BaZi ruleset identifier

pillars

Collapse all**object**

year

Collapse all**object**

stem_index

Collapse all**integer**

Heavenly Stem index 0-9

branch_index

Collapse all**integer**

Earthly Branch index 0-11

stem

Collapse all**string**

Heavenly Stem name (Jia, Yi, Bing, ...)

branch

Collapse all**string**

Earthly Branch name (Zi, Chou, Yin, ...)

animal

Collapse all**string**

Chinese zodiac animal (Rat, Ox, Tiger, ...)

element

Collapse all**string**

Wu-Xing element of the stem (Holz, Feuer, Erde, Metall, Wasser)

month

Collapse all**object**

stem_index

Collapse all**integer**

Heavenly Stem index 0-9

branch_index

Collapse all**integer**

Earthly Branch index 0-11

stem

Collapse all**string**

Heavenly Stem name (Jia, Yi, Bing, ...)

branch

Collapse all**string**

Earthly Branch name (Zi, Chou, Yin, ...)

animal

Collapse all**string**

Chinese zodiac animal (Rat, Ox, Tiger, ...)

element

Collapse all**string**

Wu-Xing element of the stem (Holz, Feuer, Erde, Metall, Wasser)

day

Collapse all**object**

stem_index

Collapse all**integer**

Heavenly Stem index 0-9

branch_index

Collapse all**integer**

Earthly Branch index 0-11

stem

Collapse all**string**

Heavenly Stem name (Jia, Yi, Bing, ...)

branch

Collapse all**string**

Earthly Branch name (Zi, Chou, Yin, ...)

animal

Collapse all**string**

Chinese zodiac animal (Rat, Ox, Tiger, ...)

element

Collapse all**string**

Wu-Xing element of the stem (Holz, Feuer, Erde, Metall, Wasser)

hour

Collapse all**object**

stem_index

Collapse all**integer**

Heavenly Stem index 0-9

branch_index

Collapse all**integer**

Earthly Branch index 0-11

stem

Collapse all**string**

Heavenly Stem name (Jia, Yi, Bing, ...)

branch

Collapse all**string**

Earthly Branch name (Zi, Chou, Yin, ...)

animal

Collapse all**string**

Chinese zodiac animal (Rat, Ox, Tiger, ...)

element

Collapse all**string**

Wu-Xing element of the stem (Holz, Feuer, Erde, Metall, Wasser)

day_master

Collapse all**string**

Day Master Heavenly Stem (e.g. Geng)

dates

Collapse all**object**

birth_local

Collapse all**string**

Local birth datetime ISO 8601

birth_utc

Collapse all**string**

UTC birth datetime ISO 8601

lichun_local

Collapse all**string**

LiChun (Start of Spring) local ISO 8601

wuxing

Collapse all**object**

Wu-Xing (Five Elements) distribution and harmony

from_planets

Collapse all**object**

Wu-Xing vector derived from planetary positions

Holz

Collapse all**number**

Wood (木) element score

Feuer

Collapse all**number**

Fire (火) element score

Erde

Collapse all**number**

Earth (土) element score

Metall

Collapse all**number**

Metal (金) element score

Wasser

Collapse all**number**

Water (水) element score

from_bazi

Collapse all**object**

Wu-Xing vector derived from BaZi stems and hidden branch elements

Holz

Collapse all**number**

Wood (木) element score

Feuer

Collapse all**number**

Fire (火) element score

Erde

Collapse all**number**

Earth (土) element score

Metall

Collapse all**number**

Metal (金) element score

Wasser

Collapse all**number**

Water (水) element score

harmony_index

Collapse all**number**

Cosine similarity between planetary and BaZi Wu-Xing vectors (0-1)

dominant_planet

Collapse all**string**

Strongest element from planetary Wu-Xing

dominant_bazi

Collapse all**string**

Strongest element from BaZi Wu-Xing

houses

Collapse all**object**

House cusps 1-12 in degrees (Placidus)

Additional properties

**number**

angles

Collapse all**object**

Chart angles: Ascendant, MC, Vertex in degrees

Additional properties

**number**

validation

Collapse all**(object | null)**

Contract validation result (only if include_validation=true)

Any of

Collapse all**(object | null)**

#0 ValidationResult

Collapse all**object**

ok

Collapse all**boolean**

Whether validation passed

error

Collapse all**(string | null)**

Error message if validation failed

Any of

Collapse all**(string | null)**

#0

**string**

#1

**null**

#1

**null**

FusionRequest

Expand all**object**

FusionResponse

Collapse all**object**

input

Collapse all**object**

Additional propertiesallowed

wu_xing_vectors

Collapse all**object**

Additional properties

Collapse all**object**

Additional properties

**number**

harmony_index

Collapse all**object**

Additional propertiesallowed

elemental_comparison

Collapse all**object**

Additional properties

Collapse all**object**

Additional properties

**number**

cosmic_state

**number**

fusion_interpretation

**string**

HTTPValidationError

Expand all**object**

PillarSpec

Expand all**object**

Position

Expand all**object**

TSTRequest

Expand all**object**

TSTResponse

Collapse all**object**

input

Collapse all**object**

Additional propertiesallowed

civil_time_hours

**number**

longitude_correction_hours

**number**

equation_of_time_hours

**number**

true_solar_time_hours

**number**

true_solar_time_formatted

**string**

TimeScaleQuality

Expand all**object**

TimeScales

Expand all**object**

ValidationError

Expand all**object**

ValidationResult

Expand all**object**

WesternRequest

Expand all**object**

WuXingDistribution

Expand all**object**

WuXingSection

Expand all**object**

WxRequest

Expand all**object**

WxResponse

Collapse all**object**

input

Collapse all**object**

Additional propertiesallowed

wu_xing_vector

Collapse all**object**

Additional properties

**number**

dominant_element

**string**

equation_of_time

**number**

true_solar_time

**number**
