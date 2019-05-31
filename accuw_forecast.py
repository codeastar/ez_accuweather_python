from tinydb import TinyDB, Query
import requests
import json, re, sys, argparse, os
from datetime import datetime  

def is_input_inputted(input_var, table, field_name):
  if input_var is None: 
    input_var = table.search(Query()[field_name])
    if input_var == []: 
      parser.print_help()
      sys.exit()
    input_var = input_var[0][field_name]  
  else: 
    table.upsert({field_name:input_var}, Query()[field_name].exists())
  return input_var

def getJSONfromUrl(url): 
  response = requests.get(url)
  json_data = json.loads(response.text)
  return json_data

def getFormattedDateTime(datestr):
  p_datestr_format = ''.join(datestr.rsplit(":", 1))
  date_object = datetime.strptime(p_datestr_format, '%Y-%m-%dT%H:%M:%S%z')
  return date_object.strftime("%H:%M %A, %d %B %Y Timezone:%z")

db = TinyDB('accuw_db.json')
Profile = db.table('Profile')
Location = db.table('Location')

#load last location, metric and API KEY
if "ACW_API_KEY" in os.environ:
    API_KEY = os.environ['ACW_API_KEY']
    #upsert it to db
    Profile.upsert({'api_key':API_KEY}, Query().api_key.exists())
else: 
    #if no key from env, get from db 
    API_KEY = Profile.search(Query().api_key)
    if API_KEY == []: 
      sys.exit("No API key found")
    API_KEY = API_KEY[0]['api_key']
 
parser = argparse.ArgumentParser(description='AccuWeather Forecast for Python')
parser.add_argument('-l', action="store", dest="location",  help='location for weather forecast, e.g. "Tokyo"') 
parser.add_argument('-m', action="store", dest="metric", choices=['c', 'f'], help='metric for weather forecast, c or f', default="c", type=str.lower )

args = parser.parse_args()

location = is_input_inputted(args.location,Profile, "last_location")     
metric = is_input_inputted(args.metric, Profile, "last_metric")   

try:
  if (Location.count(Query()) == 0): 
    url = f"http://dataservice.accuweather.com/locations/v1/topcities/150?apikey={API_KEY}"
    json_data = getJSONfromUrl(url)

    #fill up wit the most popular 150 locations      
    for p in json_data:
      Location.insert({'name': p['LocalizedName'], 'key': p['Key'], 'english_name':p['EnglishName'],
      'administrative_area':p['AdministrativeArea']['ID'], 'country': p['Country']['EnglishName']})

  location_from_db = Location.search(Query().name.matches(location, flags=re.IGNORECASE))
  
  if location_from_db == []:
    url = f"http://dataservice.accuweather.com/locations/v1/search?apikey={API_KEY}&q={location}"
    json_data = getJSONfromUrl(url)

    if json_data == []:
      sys.exit(f"No location found for '{location}' from AccuWeather API") 
    else:
      for p in json_data:
          Location.insert({'name': location, 'key': p['Key'], 'english_name':p['EnglishName'],
          'administrative_area':p['AdministrativeArea']['ID'],'country': p['Country']['EnglishName']})
          break
      location_from_db = Location.search(Location.name.matches(location, flags=re.IGNORECASE))

  location_key = location_from_db[0]['key']
  admin_area = location_from_db[0]['administrative_area']
  country = location_from_db[0]['country']
  
  #get current weather by key
  url = f"http://dataservice.accuweather.com/currentconditions/v1/{location_key}?apikey={API_KEY}&details=true"
  json_data = getJSONfromUrl(url)

  unit = "Metric" if (metric == "c") else "Imperial"
  metric_tag = "true" if (metric == "c") else "false"

  for p in json_data:
    current_weather=p["WeatherText"]
    current_temp=p["Temperature"][unit]
    wind_speed=p["Wind"]["Speed"][unit]
    date_w_format = getFormattedDateTime(p["LocalObservationDateTime"])

  char_length = 50
  print(f"Location: {location}, {admin_area}, {country}") 
  print(f"Local observation time: {date_w_format}")
  print(f"Current weather status: {current_weather}")
  print(f"Current temperature: {current_temp['Value']} {current_temp['Unit']}")
  print(f"Wind speed: {wind_speed['Value']} {wind_speed['Unit']}")
  print(f"\n{'='*char_length}")

  #5-day
  url = f"http://dataservice.accuweather.com/forecasts/v1/daily/5day/{location_key}?apikey={API_KEY}&details=true&metric={metric_tag}"
  json_data = getJSONfromUrl(url)

  print(f"5-day summery: {json_data['Headline']['Text']}")

  for d in json_data["DailyForecasts"]:
    print(f"{'-'*char_length}")
    print(f"Date: {getFormattedDateTime( d['Date'])}")
    print(f"Min temperature: {d['Temperature']['Minimum']['Value']} {d['Temperature']['Minimum']['Unit']}")
    print(f"Max temperature: {d['Temperature']['Maximum']['Value']} {d['Temperature']['Maximum']['Unit']}")
    print(f"Description: {d['Day']['LongPhrase']}")
    print(f"Rain probability: {d['Day']['RainProbability']} %")
    print(f"Wind speed: {d['Day']['Wind']['Speed']['Value']} {d['Day']['Wind']['Speed']['Unit']}")

except Exception as e: 
    print(f"Server response: {json_data}")
    sys.exit(f"Error getting data from API: {e}")