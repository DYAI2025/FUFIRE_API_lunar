# BaziRequestCollapse allobject

dateCollapse allstring ISO 8601 local date time (e.g. 2024-02-10T14:30:00)

tzCollapse allstring Timezone name

Default"Europe/Berlin" lonCollapse allnumber Longitude in degrees

Default13.405 latCollapse allnumber Latitude in degrees

Default52.52 standardCollapse allstring EnumExpand allarray Default"CIVIL" boundaryCollapse allstring EnumExpand allarray Default"midnight" strictCollapse allboolean Defaulttrue ambiguousTimeCollapse allstring EnumExpand allarray Default"earlier" nonexistentTimeCollapse allstring EnumExpand allarray Default"error"

ChartRequestCollapse allobject local_datetimeCollapse allstring ISO 8601 local datetime (e.g. 2024-02-10T14:30:00)

tz_idCollapse allstring IANA timezone name

Default"Europe/Berlin" geo_lon_degCollapse allnumber Geographic longitude in degrees

Default13.405 geo_lat_degCollapse allnumber Geographic latitude in degrees

Default52.52 dst_policyCollapse allstring DST handling: 'error' rejects nonexistent times, 'earlier'/'later' choose fold for ambiguous and shift_forward for gaps

EnumExpand allarray Default"error" bodiesCollapse all(array<string> | null) Western bodies to include (default: all available). E.g. ['Sun','Moon','Mercury','Venus','Mars','Jupiter','Saturn']

Any ofExpand all(array<string> | null) include_validationCollapse allboolean Embed /validate result in response

Defaultfalse time_standardCollapse allstring Time standard for BaZi calculation

EnumExpand allarray Default"CIVIL" day_boundaryCollapse allstring Day change policy for BaZi

EnumExpand allarray Default"midnight"

FusionRequestCollapse allobject dateCollapse allstring ISO 8601 local date time

tzCollapse allstring Timezone name

Default"Europe/Berlin" lonCollapse allnumber Longitude in degrees

latCollapse allnumber Latitude in degrees

ambiguousTimeCollapse allstring EnumCollapse allarray #0"earlier" #1"later" Default"earlier" nonexistentTimeCollapse allstring EnumCollapse allarray #0"error" #1"shift_forward" Default"error" bazi_pillarsCollapse all(object | null) Ba Zi pillars (optional — computed automatically if omitted)

Any ofCollapse all(object | null) #0Collapse allobject Additional propertiesCollapse allobject Additional propertiesstring #1null

TSTRequestCollapse allobject dateCollapse allstring ISO 8601 local date time

tzCollapse allstring Timezone name

Default"Europe/Berlin" lonCollapse allnumber Longitude in degrees

ambiguousTimeCollapse allstring EnumCollapse allarray #0"earlier" #1"later" Default"earlier" nonexistentTimeCollapse allstring EnumCollapse allarray #0"error" #1"shift_forward" Default"error"

WesternRequestCollapse allobject dateCollapse allstring ISO 8601 local date time

tzCollapse allstring Timezone name

Default"Europe/Berlin" lonCollapse allnumber Longitude in degrees

Default13.405 latCollapse allnumber Latitude in degrees

Default52.52 ambiguousTimeCollapse allstring EnumCollapse allarray #0"earlier" #1"later" Default"earlier" nonexistentTimeCollapse allstring EnumCollapse allarray #0"error" #1"shift_forward" Default"error"

WxRequestCollapse allobject dateCollapse allstring ISO 8601 local date time

tzCollapse allstring Timezone name

Default"Europe/Berlin" lonCollapse allnumber Longitude in degrees

latCollapse allnumber Latitude in degrees

ambiguousTimeCollapse allstring EnumCollapse allarray #0"earlier" #1"later" Default"earlier" nonexistentTimeCollapse allstring EnumCollapse allarray #0"error" #1"shift_forward" Default"error"
