import {useEffect} from 'react';

/** Native, once-only entrance motion. Never intercept wheel/touch scrolling. */
export function useSiteMotion(paused: boolean) {
  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    let observer: IntersectionObserver | undefined;
    const animations = new Set<Animation>();
    const stop = () => {
      observer?.disconnect();
      animations.forEach(animation => animation.cancel());
      animations.clear();
    };
    const setup = () => {
      stop();
      document.documentElement.classList.toggle('motion-reduced', preference.matches || paused);
      if (paused || preference.matches || typeof Element.prototype.animate !== 'function') return;
      observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
          if (!entry.isIntersecting) return;
          observer?.unobserve(entry.target);
          const animation = entry.target.animate(
            [{transform:'translateY(12px)',opacity:.6},{transform:'translateY(0)',opacity:1}],
            {duration:420,easing:'cubic-bezier(.22,.72,.25,1)'},
          );
          animations.add(animation);
          animation.onfinish = () => animations.delete(animation);
        });
      }, {threshold:.12});
      document.querySelectorAll('.hero-copy,.applications-intro,.evidence-heading,.pathway-heading,.faq-heading,[data-reveal]').forEach(element => observer?.observe(element));
    };
    setup();
    preference.addEventListener('change',setup);
    return () => {stop();preference.removeEventListener('change',setup);document.documentElement.classList.remove('motion-reduced');};
  },[paused]);
}
