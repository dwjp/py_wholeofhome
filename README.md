# py_wholeofhome

This package implements the various calculations for the Nationwide House Energy Rating Scheme (NatHERS) whole-of-home methodology (https://www.nathers.gov.au/whole-of-home). This includes heating/cooling, hot water, cooking and more, but not the core thermal envelope modelling which estimates the heating and cooling demand of a given building.

It's a work-in-progress!

Currently, designed to implement Rev 10.1 of the Calculation Method Paper.

This package is not officially affiliated with NatHERS and is not an accredited rating tool. It's intended for research and the creation of other tools that can make use of the underlying methodology. I've used a permissive license (MIT), but I'd encourage any users, whether government, commercial or academic, to get in touch with me to discuss how we can work together to make this a more useful tool for the community. Let's not waste time and money on more proprietary tools that implement exactly the same thing! Please get in touch if you're interested in helping out. We're always on the lookout to hire passionate python energy/climate folks at BOOMPower too.

If this package is useful, please consider acknowledging the authors in your work.


## What's working

- Calculation of hourly lighting, plug loads, hot water (mostly), cooking load profiles.

## Still todo

- Heating/cooling, work in progress still.
- Electric hot water solar diverter
- Pool pumps
- Get higher precision reference data from NatHERS team, more test cases.
- Some of the wrapper calculations used by the official ratings, carbon costs, etc.
- Tidier package layout 

## Not Covered

We probably won't be implementing solar or battery modelling, as NREL already have a much more sophisticated open-source model: https://github.com/NREL/ssc

We also aren't doing any thermal modelling here, since the CSIRO Chenath model is proprietary, unfortunately.


## Getting started

We're using poetry, see pyproject.toml for dependencies (mostly vanilla python + pandas + numpy)

The test cases are a useful way to see how to talk to the package. 