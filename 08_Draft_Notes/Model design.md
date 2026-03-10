# General Fields
## Literature
* [Wildfire Risk Modeling (Oliveira, S et al. 2021)](00_Literature/Phase 1/00_Wildfire_Risk_Modeling_Oliviera.pdf)
* [Global Forest Fire Assessment Methods: A comparative analysis of Hazard, Susceptibility, and Vulnerability Approaches in Different Landscapes](00_Literature/Phase 1/02_Global_Forest_Fire_Mihajlovski.pdf)
# Broad Topics
## Wildfire
- [[Fire_in_Earth_System.pdf#page=2&selection=14,27,27,1&color=yellow|The global scope of fire has been revealed only recently by satellite observations available beginning in the 1980s (24) (Fig. 2). This record shows a strong association between high fire activity and areas of intermediate primary production, particularly in tropical savannas (25).]]
## Wildfire risk modeling
### Notes
- **Wildfire risk modeling** is earning relevance in several wildfire phases, ==covering prevention, suppression, and recovery==, and encouraging the development of different products and tools. See: [[00_Wildfire_Risk_Modeling_Oliviera.pdf#page=1&selection=21,22,24,32&color=yellow|here.]]
- Wildfire risk modeling includes different approaches and relate to different aspects of risk. See: [[00_Wildfire_Risk_Modeling_Oliviera.pdf#page=1&selection=24,33,28,20&color=yellow|here.]]:
	- **Likelihood and Hazard:**
		- [[00_Wildfire_Risk_Modeling_Oliviera.pdf#page=1&selection=150,20,152,25&color=yellow|This approach responds to specific questions: (1) how it starts, (2) when it happens, (3) where it occurs, and (4) how it will grow.]]
	- **Exposure:**
		- [[00_Wildfire_Risk_Modeling_Oliviera.pdf#page=3&selection=2,0,22,20&color=yellow|Wildfire exposure evaluates which assets, and to what extent, are located in fire-prone areas. It results from the analysis of fire occurrence, likelihood, or hazard in relation to HVRAs, using historical fire data or by coupling stochastic and probabilistic wildfire simulations with the spatial distribution of HVRAs.]] [[General Concepts#^87e658]]
	- **Vulnerability:**
		- [[00_Wildfire_Risk_Modeling_Oliviera.pdf#page=3&selection=71,0,85,1&color=yellow|Represents the potential for loss as a result of wildfires. As a measure of potential wildfire impacts, it depends on the conditions of the wildfire and on the characteristics of the affected assets.]]
	- **Coping capacity and response:**
		- [[00_Wildfire_Risk_Modeling_Oliviera.pdf#page=3&selection=127,0,130,6&color=yellow|Models of alternative actions and behavior choices that can modify the response capacity to wildfire events have emerged, assessing evacuation, local sheltering, or stay-at-home option.]]
	- **Wildfire risk:**
		- [[00_Wildfire_Risk_Modeling_Oliviera.pdf#page=3&selection=237,0,238,46&color=yellow|Wildfire risk assessment intends to provide an integrated view of fire likelihood and consequences.]]
		- Each component previously described is considered in the model:
			- [[00_Wildfire_Risk_Modeling_Oliviera.pdf#page=3&selection=239,0,256,57&color=yellow|The relative contribution of each component, previously described, is evaluated, then aggregated and summarized in quantitative indices or categories, providing a rating of wildfire occurrence conditions and potential impacts, and further combined with mapping and zoning tools to identify priority areas for intervention.]]
		- Wildfire risk framework:
			![Image](C:\Users\pmedi\Documents\09_Research\Wildfires\01_Images\01_wildfire_risk_framework.png)
			[[04_Deep_learning_Wildfire_Risk_Prediction_Xu.pdf#page=2&selection=65,0,65,77&color=yellow|Figure 1: The generalized wildfire risk framework proposed by Miller and Ager]]
		- This framework emphasizes the impact of the wildfire rather than just the occurrence. In the document words:
			- [[04_Deep_learning_Wildfire_Risk_Prediction_Xu.pdf#page=2&selection=32,6,40,33&color=yellow|This framework emphasizes the impact of wildfires on human activities and the environment rather than solely considering the probability of occurrence. For instance, low-intensity and low-impact wildfires might not significantly affect areas of concern, meaning that a high likelihood of wildfire occurrence does not necessarily equate to high wildfire risk.]]
- **Wildifire ignitions are mostly originated from antropogenic activity:** 
	- [[05_Conceptual_Clarity_Fire_Science_Toy_opazo.pdf#page=8&selection=21,43,24,6&color=yellow|In most cases, climatic variables are treated as the main determinants of ignition, when global evidence shows that approximately 90% of wildfires originate from direct anthropogenic causes, whether accidental or intentional]]
	- [[05_Conceptual_Clarity_Fire_Science_Toy_opazo.pdf#page=8&selection=28,3,31,25&color=yellow|This perspective tends to assign climate a causal responsibility that actually lies with human activity, shifting the discussion away from local drivers (such as land-use, agricultural practices, territorial management, or urban expansion) toward a more abstract environmental framework.]]
	- Climatic conditions contribute to the predisposition of a landscape to burn, rather than the cause of ignition. [[05_Conceptual_Clarity_Fire_Science_Toy_opazo.pdf#page=8&selection=31,25,33,73&color=yellow|Link.]]
- **Fire occurence:** [[05_Conceptual_Clarity_Fire_Science_Toy_opazo.pdf#page=11&selection=16,76,23,50&color=yellow|efers to the exact moment in which a fire starts, that is, the ignition process that initiates combustion, which is uncontrolled and may phase into a wildfire [ 86 ]. For this event to take place, there must be an ignition source, either anthropic or natural.]]
- **Fire Spread:** [[05_Conceptual_Clarity_Fire_Science_Toy_opazo.pdf#page=11&selection=30,0,30,62&color=yellow|is the horizontal expansion of a fire once it has been ignited.]]
### Wildfire modeling sub topics
#### Forest Fire
[[02_Global_Forest_Fire_Mihajlovski.pdf#page=2&selection=110,48,119,61&color=yellow|Forest fires refer specifically to uncontrolled fires occurring in forested ecosystems, including woodlands, timber stands, and forest-adjacent areas with significant tree cover [ 6 ]. While wildfires encompass a broader spectrum of vegetation fires, including grasslands, shrublands, and mixed vegetation types, forest fires present unique vulnerability characteristics due to canopy structure, fuel load dynamics, and forest-specific management considerations [2].]]

### Read more:
- Cellular automata
# Models
## Machine learning
*Higher adoption in American and European studies. These methods demonstrate superior performance in handling large, heterogeneous datasets combining meteorological, topographical, and anthropogenic variables.* [[02_Global_Forest_Fire_Mihajlovski.pdf#page=8&selection=117,22,126,7&color=yellow|Reference.]]
- **Random Forest**: 
- Support Vector Machine
- Decision Tree
- XGBoost
## Statistical and Probabilistic methods
*Through the analysis, S&P methods show great uncertainty quantification, probabilistic interpretation, and an established theoretical foundation.*
- Frequency ratio
- **Maximum Entropy (MAXENT)**
- Logistic Regression
- **Bayesian Networks**
- Naive Bayes
- Principal component analysis
- Multivariate logistic regression
## Fire simulation
- FARSITE
- FSim
- FlamMap
- Burn-P3
- Cellular automata
## Multi-Criteria Decision Analysis
*Its utilization recognizes that wildfire vulnerability is a multidimensional problem, requiring integrated assessment frameworks.* [[02_Global_Forest_Fire_Mihajlovski.pdf#page=8&selection=112,0,117,21&color=yellow|Reference.]]
* **Analytical Hierarchical Process (AHP)**: Is the most utilized method within MCDA. [[02_Global_Forest_Fire_Mihajlovski.pdf#page=9&selection=89,0,102,41&color=yellow|Reference.]]
* Fuzzy-Analytical Hierarchical Process (FAHP)
* Modified AHP (M-AHP)
* Gray Relativity Analysis
# Possible Research Topic
- [[00_Wildfire_Risk_Modeling_Oliviera.pdf#page=3&selection=285,29,287,45&color=important|In Brazil, a fire risk map was obtained by combining historical fire data with a Kernel density estimator to determine critical areas]]
- [[00_Wildfire_Risk_Modeling_Oliviera.pdf#page=4&selection=1,43,15,49&color=important|A European initiative has also proposed a composite risk index that aggregates three dimensions: hazard and exposure, vulnerability, and lack of coping capacity, applicable at different spatial scales and for multiple hazards]]
- 