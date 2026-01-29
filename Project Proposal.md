*Draft version*

---
# Introduction
*Topics to explore on Introduction*
- Wildfire Impact
	- Wildfire impact on: natural resources, human life, economy
	- Wildfire incidence in Paraguay, in the Chaco
- Wildfire mitigation efforts
	- What is done, when
	- Resources, mention modeling
- Wildfire risk modeling overview
	- MCDM modeling in Fire risk modeling
	- Aspects considered: hazard, exposure, sensitivity, adaptive capacity
	- Shortcomings of MCDM
	- Monte Carlo simulations and uncertainty
- Objectives
	- Develop a wildfire risk model adjusted for the Paraguayan Chaco
	- Run Monte Carlo simulations to asses uncertainties associated with AHP weights
	- Validate the model against FIRMS fire data

**Wildfire Impact**
Wildfires are understood to be a recurrent earth system process contributing to the delineation of ecological boundaries through fire regimes, and atmospheric dynamics through the release of carbon ([[Fire_in_Earth_System.pdf#page=2&selection=76,0,81,13&color=yellow|1]], [[Harrison_2021_Environ._Res._Lett._16_125008.pdf#page=3&selection=190,7,225,6&color=yellow|2]]). Most recently, anthropogenic driven land use change and climate change have altered these dynamics through ecological fragmentation, increased ignition sources, and prolonged extreme weather events ([[Harrison_2021_Environ._Res._Lett._16_125008.pdf#page=8&selection=60,14,106,6&color=yellow|2]], [[05_Conceptual_Clarity_Fire_Science_Toy_opazo.pdf#page=2&selection=123,0,152,70&color=yellow|3]], [[03_Spatiotemporal_analysis_of_wildfires.pdf#page=2&selection=56,0,89,2&color=yellow|4]]). 
# Study Area
# Data
# Methods
# Results and Discussion
# Conclusion
# References
1. [Fire in the Earth System](00_Literature/Foundational/Fire_in_Earth_System.pdf)
2. [Understanding and modelling wildfire regimes](00_Literature/Paraguayan Wildfires/17_Fires_in_the_Chaco.pdf)
3. [Conceptual Clarity in Fire Science](00_Literature/Phase 1/05_Conceptual_Clarity_Fire_Science_Toy_opazo.pdf)
4. [Spatiotemporal analysis of wildfires](00_Literature/Paraguayan Wildfires/1-s2.0-S0048969724069808-main.pdf)
5. 
# Email to Dr Resop


Hi Jonathan,

Hope everything is going well.

I have been reading and learning more about the wildfire modeling field, and found two specific topics that got my attention:

- Wildfire spread models
- Wildfire Risk Assessment modeling

**Wildfire spread models**

To model wildfire spread, I propose to use Cellular Automata either in Net Logo or using Python (I saw that there are some specialized libraries). To account for uncertainty, I'd plan to run Monte Carlo simulations and vary some of the inputs, as well as including stochastic ignition points. 

Then I would do an analysis of the results, showing a map of more probable burned areas and priority communities for a wildfire prevention plan.

**Wildfire Risk Assessment modeling**

For the wildfire risk model, I would like to implement a risk model with AHP, that outputs 3 wildfire risk surfaces based on 3 main assets: 1) Population, 2) Natural resources, and 3) Infrastructure. 

The main model will have 4 inputs: 1) Fire hazard, 2) Exposure, 3) Sensitivity, and 4) Adaptive capacity. 3 of them are outputs of inner models:
- Exposure: Depending on the asset risk being modeled, will be: population density, infrastructure density, and forest land cover/protected areas
- Sensitivity: AHP model adapted to the asset being modeled
- Adaptive capacity: AHP model adapted to the asset being modeled
- Fire hazard: Will be the output of a random forest model developed on the modeling class, the model predicts wildfire likelihood.

Since subjectivity is an issue with the weights in suitability modeling, my idea is to make the results more robust by running Monte Carlo simulations modifying the weights of the inputs with a base made on available literature.

--

I think that combining these two might be too complex and the 12 week timeframe too short to have a good result, although please advise if you belief that could be a good option.

I will be submitting an application to graduate this Spring, so I will be submitting my advising appointment with Dr. Ma soon after deciding the capstone topic.

Many thanks,
Paulo