import { useEffect, useMemo, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { AdminReport } from "./api";

type Props = {
  rows: AdminReport[];
  selectedId?: string | null;
  onSelect: (row: AdminReport) => void;
};

export default function ReportsMap({ rows, selectedId, onSelect }: Props) {
  const el = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);

  const points = useMemo(
    () =>
      rows.filter(
        (r) =>
          typeof r.latitude === "number" &&
          typeof r.longitude === "number" &&
          Number.isFinite(r.latitude) &&
          Number.isFinite(r.longitude)
      ),
    [rows]
  );

  useEffect(() => {
    if (!el.current || mapRef.current) return;
    const map = L.map(el.current, { zoomControl: true, attributionControl: true });
    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap · CARTO",
      maxZoom: 16,
    }).addTo(map);
    const layer = L.layerGroup().addTo(map);
    map.setView([6.9271, 79.8612], 8);
    mapRef.current = map;
    layerRef.current = layer;
    return () => {
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
    };
  }, []);

  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;
    layer.clearLayers();
    const latLngs: L.LatLngExpression[] = [];
    for (const r of points) {
      const color = r.report_type === "LOST" ? "#c24d49" : "#1f6b53";
      const selected = r.report_id === selectedId;
      const marker = L.circleMarker([r.latitude as number, r.longitude as number], {
        radius: selected ? 11 : 8,
        color,
        weight: selected ? 3 : 2,
        fillColor: color,
        fillOpacity: selected ? 1 : 0.78,
      });
      marker.bindTooltip(
        `${r.report_type} · ${r.title || "Untitled"}`,
        { direction: "top" }
      );
      marker.on("click", () => onSelectRef.current(r));
      marker.addTo(layer);
      latLngs.push([r.latitude as number, r.longitude as number]);
    }
    if (latLngs.length === 1) {
      map.setView(latLngs[0], 13);
    } else if (latLngs.length > 1) {
      map.fitBounds(L.latLngBounds(latLngs).pad(0.18));
    }
    setTimeout(() => map.invalidateSize(), 80);
  }, [points, selectedId]);

  return (
    <div className="reports-map-wrap">
      <div ref={el} className="reports-map" />
      {!points.length && (
        <div className="reports-map-empty">No mapped items in this filter. Pins use fuzzed areas only.</div>
      )}
    </div>
  );
}
