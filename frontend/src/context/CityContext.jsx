import { createContext, useContext, useEffect, useState } from "react";

export const CITIES = ["Chennai", "Delhi", "Mumbai", "Bengaluru", "Hyderabad", "Kolkata"];
const Ctx = createContext(null);

export function CityProvider({ children }) {
  const [city, setCity] = useState(() => {
    try { const c = localStorage.getItem("cs_city"); return CITIES.includes(c) ? c : "Chennai"; } catch { return "Chennai"; }
  });
  useEffect(() => { try { localStorage.setItem("cs_city", city); } catch { /* storage unavailable */ } }, [city]);
  return <Ctx.Provider value={{ city, setCity, cities: CITIES }}>{children}</Ctx.Provider>;
}

export const useCity = () => useContext(Ctx);
