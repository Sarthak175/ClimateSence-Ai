import ManualPredictor from "../components/ManualPredictor";
import { PageHeader } from "../components/ui";
import { useCity } from "../context/CityContext";

export default function ManualInput() {
  const { city } = useCity();
  return (
    <>
      <PageHeader title={`${city} · Manual input`} subtitle="Type your own weather values and the trained model returns the next-day maximum temperature, its uncertainty and an explanation. Nothing is guessed - every field is required." />
      <ManualPredictor />
    </>
  );
}
