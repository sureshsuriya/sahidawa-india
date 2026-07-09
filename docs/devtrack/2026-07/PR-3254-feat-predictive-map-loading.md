# PR #3254 — Feat/predictive map loading

> **Merged:** 2026-07-07 | **Author:** @pushtikadia | **Area:** Frontend | **Impact Score:** 5 | **Closes:** #3252

## What Changed

We integrated our existing `usePredictivePrefetch` hook into the `MapView` component to enable predictive background loading of pharmacy and ASHA worker data. The data-fetching logic was refactored out of the mounting `useEffect` hook into a standalone `loadForCoords` function. Finally, we wrapped the Leaflet `MapContainer` in a ref-monitored container `div` to trigger background API requests as the map element approaches the user's viewport.

## The Problem Being Solved

Previously, map data was fetched reactively only after the `MapView` component had fully mounted and the user's geolocation was resolved. In rural or low-bandwidth environments—which represent a significant portion of SahiDawa's target demographic—this sequential execution resulted in noticeable latency, leaving users waiting on empty map states or loading spinners. Furthermore, the fetching logic was tightly coupled inside a monolithic `useEffect` hook, making it impossible to trigger prefetching based on viewport intersection or scroll behavior.

## Files Modified

- `apps/web/components/map/MapView.tsx`

## Implementation Details

### Standalone Fetching Refactor
We extracted the core data-fetching logic into a reusable, asynchronous `loadForCoords` function:
```typescript
const loadForCoords = async (lat: number, lng: number) => {
    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;
    setLoading(true);
    setError(null);
    try {
        const res = await fetch(`/api/map/nearby?lat=${lat}&lng=${lng}&radius_km=10`, {
            signal: controller.signal,
        });
        if (!res.ok) throw new Error("Map API error");
        const data = await res.json();
        setPharmacies(data.pharmacies || []);
        setAshaWorkers(data.asha_workers || []);
    } catch (err) {
        if (!(err instanceof DOMException && err.name === "AbortError")) setError("Unable to load data.");
    } finally {
        setLoading(false);
    }
};
```
This function manages an `AbortController` ref (`abortControllerRef`) to cancel stale, in-flight requests when coordinates change rapidly, preventing race conditions.

### Predictive Prefetch Integration
We initialized the `usePredictivePrefetch` hook, passing a `preloadQuery` callback and an intersection threshold:
```typescript
const mapContainerRef = usePredictivePrefetch({
    preloadQuery: async () => {
        if (userLocation) await loadForCoords(userLocation[0], userLocation[1]);
    },
    threshold: 0.2,
});
```
The `threshold: 0.2` configuration ensures that when 20% of the map container wrapper enters the viewport, the background prefetch is triggered.

### DOM Binding
We wrapped the Leaflet `MapContainer` inside a wrapper `div` and attached the returned `mapContainerRef`:
```tsx
<div ref={mapContainerRef as any}>
    <MapContainer center={userLocation} zoom={13} style={{ height: "500px", width: "100%" }}>
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        {/* Markers */}
    </MapContainer>
</div>
```

## Technical Decisions

### Leveraging Network-Aware Prefetching
Instead of writing a custom `IntersectionObserver` inside `MapView`, we utilized our existing `usePredictivePrefetch` hook. This hook automatically respects network constraints (e.g., checking `navigator.connection` to skip prefetching on slow 2G/3G connections or when Save-Data mode is enabled). This is a critical optimization for our rural users who may be operating on metered or unstable mobile networks.

### Decoupling HTML Entity Decoding
We removed the inline DOM-based decoding (`decodeHtmlEntities`) from the network response parsing step inside `loadForCoords` to keep the fetch cycle lightweight and fast, deferring any complex string manipulation to the UI rendering layer.

### AbortController Ref
We retained the `AbortController` pattern to prevent race conditions when coordinates change rapidly or when multiple prefetch/fetch cycles overlap.

## How To Re-Implement (Contributor Reference)

To implement predictive prefetching on another data-heavy component, follow these steps:

1. **Import the Hook**: Import `usePredictivePrefetch` from the hooks directory:
   ```typescript
   import { usePredictivePrefetch } from "../../hooks/usePredictivePrefetch";
   ```
2. **Isolate Fetching Logic**: Ensure your data-fetching logic is isolated into a standalone function (e.g., `loadData()`) that handles loading states, error states, and utilizes an `AbortController` ref to cancel stale requests.
3. **Initialize the Hook**: Call the hook inside your component, passing the fetch function to `preloadQuery` and setting a viewport intersection `threshold`:
   ```typescript
   const containerRef = usePredictivePrefetch({
       preloadQuery: async () => {
           await loadData();
       },
       threshold: 0.2,
   });
   ```
4. **Bind the Ref**: Attach the returned `ref` to the outermost wrapper element of the component you want to monitor.
5. **Handle Fallbacks**: Ensure that if the user's location or context is not yet available, the prefetch query fails gracefully or waits until the required dependencies are resolved.

## Impact on System Architecture

- **Reduced Latency**: Significantly improves perceived performance and reduces Time-to-Interactive (TTI) for the map feature by loading data before the user fully scrolls to the map.
- **Standardized Performance Patterns**: Establishes a reusable pattern for viewport-based predictive loading across other data-heavy components in the SahiDawa web app.
- **Resource Conservation**: Protects backend resources and user data plans by utilizing network-aware prefetching boundaries.

## Testing & Verification

- **Manual Verification**: Scroll the map container into view on a simulated slow network (using Chrome DevTools Network throttling) to verify that the API request is dispatched before the map is fully visible.
- **Data-Saver Check**: Verify that prefetching is bypassed when the browser's Save-Data option is enabled or when the connection type is 'slow-2g' or '2g' (handled by the underlying hook).
- **Race Conditions**: Rapidly trigger geolocation changes or scroll in/out of the viewport to ensure the `AbortController` successfully cancels stale requests and prevents state updates on unmounted components.