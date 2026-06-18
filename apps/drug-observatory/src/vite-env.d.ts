/// <reference types="vite/client" />

// world-atlas ships topojson as JSON; we only ever hand it to react-simple-maps.
declare module 'world-atlas/*.json' {
  // Topojson blob handed straight to react-simple-maps; not worth typing.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const value: any
  export default value
}
