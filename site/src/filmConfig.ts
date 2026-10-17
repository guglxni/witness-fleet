const configured=import.meta.env.VITE_FILM_URL?.trim();
export const DEFAULT_FILM_URL=configured||'/media/launch.mp4';
