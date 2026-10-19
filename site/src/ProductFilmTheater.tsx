import revisedTranscript from './revised-transcript.json';
import './youtube-film.css';

const demoUrl = import.meta.env.VITE_DEMO_URL?.trim() || 'https://witness-fleet-guglxni.eastus.cloudapp.azure.com/demo';
const youtubeUrl = 'https://youtu.be/v7P9KVyTrWY';

export function ProductFilmTheater() {
 return <section className="film-section" id="film" aria-labelledby="film-title">
  <div className="film-header">
   <div><p className="section-kicker">THE PRODUCT / THE PROOF</p><h2 id="film-title">A bigger picture.<br/><em>An inspectable record.</em></h2></div>
   <span className="film-duration">FALKORDB FILM · SOUND ON</span>
  </div>
  <p className="film-context-note">This film explains the product with recorded simulation and illustrative scenes. For the interactive system, <a href={demoUrl} target="_blank" rel="noreferrer">run the working simulation ↗</a>.</p>
  <div className="film-theater">
   <div className="film-frame-bar"><span>WITNESS FLEET / BUILT WITH FALKORDB</span><span>USER-INITIATED PLAYBACK</span></div>
   <div className="film-player youtube-player">
    <iframe
     title="Witness Fleet × FalkorDB — YouTube video player"
     src="https://www.youtube-nocookie.com/embed/v7P9KVyTrWY?autoplay=0&controls=1&playsinline=1&rel=0"
     width="560" height="315" loading="lazy"
     referrerPolicy="strict-origin-when-cross-origin"
     allow="accelerometer; encrypted-media; gyroscope; picture-in-picture; fullscreen"
     allowFullScreen
    />
   </div>
   <p className="youtube-fallback"><a href={youtubeUrl} target="_blank" rel="noreferrer">Watch on YouTube ↗</a><span>Hosted on YouTube · no autoplay</span></p>
  </div>
  <div className="film-description">
   <div>
    <p>Official FalkorDB branding and a source-grounded look at the property graph, read-only Cypher, provenance and conditional claims. AI concept scenes are illustrative; schema graphics are explanatory; MuJoCo footage is recorded simulation. Witness Fleet code makes the authorization decisions. No physical deployment or certification is claimed.</p>
    <a href="/media/campaign/CREDITS-FALKORDB.md" target="_blank" rel="noreferrer">Production credits &amp; usage rights ↗</a>
   </div>
   <details className="transcript-disclosure"><summary>Transcript &amp; captions <span aria-hidden="true">＋</span></summary>
    <div className="transcript-text">{revisedTranscript.map((paragraph,index)=><p key={index}>{paragraph}</p>)}
     <p><a href="/media/campaign/product-ad-falkordb.vtt" download>English captions</a></p>
    </div>
   </details>
  </div>
 </section>;
}
