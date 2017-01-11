import datetime

import pandas as pd

from Provider import Provider

from DataBaseProxy import DataBaseProxy
dbp = DataBaseProxy()
            
class Enjoy(Provider):
    
    def __init__ (self, city):
        self.name = "enjoy"
        self.city = city
    
    def select_data (self, city, by, *args):
        
        if by == "timestamp" and len(args) == 2:
            self.start, self.end = args
            self.cursor = dbp.query_raw_by_time(self.name, city, self.start, self.end)
            print "Data selected!"
            
        return self.cursor
        
    def get_fields(self):
        
        self.cursor.rewind()
        sample_columns = pd.DataFrame(self.cursor.next()["state"]).columns
        for doc in self.cursor:
            columns = pd.DataFrame(doc["state"]).columns
            if len(columns.difference(sample_columns)):
                print "Warning: different fields for the same provider"
            
        self.fields = columns
        return self.fields
        
    def get_fleet(self):

        self.cursor.rewind()        
        doc = self.cursor.next()
        current_fleet = pd.Index(pd.DataFrame(doc["state"])\
                                 .loc[:, "car_plate"].values)
        self.fleet = current_fleet
        for doc in self.cursor:
            current_fleet = pd.Index(pd.DataFrame(doc["state"])\
                                     .loc[:, "car_plate"].values)
            self.fleet = self.fleet.union(current_fleet)
            
        print "Fleet acquired!"
            
        return self.fleet

    def get_parks_v2 (self):
        
        self.cursor.rewind()
        doc = self.cursor.next()

        cars_status = pd.DataFrame(index = self.fleet.values)
        cars_lat = pd.DataFrame(index = self.fleet.values)
        cars_lon = pd.DataFrame(index = self.fleet.values)
        
        def update_cars_status ():
            df = pd.DataFrame(doc["state"])

            parked = df[["car_plate", "lat", "lon"]]
            cars_status.loc[parked["car_plate"].values, doc["timestamp"]] = "parked"            
            cars_lat.loc[parked["car_plate"].values, doc["timestamp"]] = \
                pd.Series(data=df["lat"].values,
                          index=parked["car_plate"].values)                
            cars_lon.loc[parked["car_plate"].values, doc["timestamp"]] = \
                pd.Series(data=df["lon"].values,
                          index=parked["car_plate"].values)            
            booked = self.fleet.difference(df["car_plate"])
            cars_status.loc[booked.values, doc["timestamp"]] = "booked"
        
        for doc in self.cursor:
            update_cars_status()
            
        cars_status = cars_status.T
        cars_lat = cars_lat.T
        cars_lon = cars_lon.T

        global_status = {}

        for car in cars_status:

            car_status = cars_status[car]
            car_status = car_status.loc[car_status.shift(1) != car_status]

            car_lats = cars_lat[car]
            car_lats = car_lats.loc[car_status.index]

            car_lons = cars_lon[car]
            car_lons = car_lons.loc[car_status.index]
                                
            car_df = pd.DataFrame()
            car_df["status"] = car_status.values
            car_df["start"] = car_status.index
            car_df["lat"] = car_lats.values
            car_df["lon"] = car_lons.values
            car_df["start_lat"] = car_df["lat"].shift(1)
            car_df["start_lon"] = car_df["lon"].shift(1)
            car_df["end_lat"] = car_df["lat"].shift(-1)
            car_df["end_lon"] = car_df["lon"].shift(-1)
            
            car_df["end"] = car_df["start"].shift(-1)
            car_df.loc[:,"end"].iloc[-1] = self.end

            global_status[car] = car_df

            parks = car_df[car_df.status == "parked"]
            
            parks = parks.dropna(axis=1, how="all")
            parks = parks.drop("status", axis=1)
            
            for park in parks.T.to_dict().values():
                park["provider"] = self.name
                park["city"] = self.city
                dbp.insert_park_v2(self.city, park)
                
        return cars_status, global_status

def test():
    
    enjoy = Enjoy("torino")
    
    end = datetime.datetime(2016, 12, 10, 0, 0, 0)
    start = end - datetime.timedelta(days = 1)
       
    enjoy.select_data("torino","timestamp", start, end)    
    enjoy.get_fields()
    enjoy.get_fleet()
    
#    for car in list(enjoy.fleet):
#        enjoy.get_parks(car)

    t = enjoy.get_parks_v2()
        
    return enjoy, t
    
enjoy, t = test()
