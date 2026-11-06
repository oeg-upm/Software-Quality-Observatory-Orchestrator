# SALTbot: Software and Article Linker Toolbot
[![Project Status: Active – The project has reached a stable, usable state and is being actively developed.](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active) [![DOI](https://zenodo.org/badge/490763453.svg)](https://zenodo.org/badge/latestdoi/490763453)


## DESCRIPTION

  This repository contains the implementation of a tool designed to link Scientific Articles and their Software pages on Wikibase graphs.
  
  SALTBot is proposed as a Wikidata bot, with its own page [here](https://www.wikidata.org/wiki/User:SALTbot). It is maintained and run by the Ontology Engineering Group and Universidad Politécnica de Madrid.


## REQUIRENMENTS
- Python >=3.11,<3.13
- poetry: `pip install poetry`
- Docker in case you want to use it by Docker image

## INSTALLATION
    
  1. Clone repository: `git clone https://github.com/SoftwareUnderstanding/SALTbot`
  
  **Recomendation:** config poetry to have the environments inside the repository `poetry config virtualenvs.in-project true --local`
  2. inside the repository, install the poetry environment: `poetry install`
3. Enable the environment: `. .venv/bin/activate` 
4. Configure Saltbot:
  - Manually: execute `saltbot configure` & fill the features
  - By Script:create the `.env` file (use .env.example as template)  & fill the features:
      ```
      MEDIAWIKI_API_URL= 
      WIKIBASE_USER= # Mandatory, your wikibase user bot
      WIKIBASE_PASSWORD=  # Mandatory, your wikibase user pwd
      GITHUB_API_TOKEN=   # Recommended, due to GithubApiLimits
      SPARQL_ENDPOINT_URL=
      WIKIBASE_URL=
      ``` 
  after that, run the script `configure_from_env.sh`

If you want to use the docker implementation create the docker image: `docker build -t saltbot .` 

  
 
  


*MODIFICAR USAGE*

## USAGE
### Configure
Before running SALTbot, you must first configure your login credentials and wikibase using the configure command
```console
python SALTbot.py configure
```
You can invoke this command using -a as argument to skip the Wikibase configuration and target Wikidata automatically 
SALTbot will then prompt you for you login information and the required wikibase URLs. If left blank, the URLs will default to Wikidata's respective values
An example of the Wikibase configuration using Wikidatas values would be the following

```console
MEDIAWIKI_API_URL = https://www.wikidata.org/w/api.php
SPARQL_ENDPOINT_URL = https://query.wikidata.org/
WIKIBASE_URL = https://www.wikidata.org
```
### Running
Once configured, execute SALTbot using

```console
python SALTbot.py run  [ARGS]
```

 For more info, run:
 ```console
 python SALTbot.py [COMMAND] --help
 ```
 
 ## Citation
 If you use SALTbot, please use the following citation:
 ```
 @article{bolinches2023saltbot,
  title		   = {SALTBot: Linking Software and Articles in Wikidata},
  author	   = {Bolinches, Jorge and Garijo, Daniel},
  year         = {2023},
  booktitle    = {Proceedings of the Wikidata Workshop 2023 co-located with 22nd International Semantic Web Conference (ISWC 2023)},
  publisher    = {CEUR-WS.org},
  series       = {{CEUR} Workshop Proceedings},
  volume       = {3640},
  url          = {https://ceur-ws.org/Vol-3640/paper12.pdf}
}

 ```

  
