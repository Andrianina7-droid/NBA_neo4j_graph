from neo4j import GraphDatabase

class NBASystem:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def run(self, query, **kwargs):
        with self.driver.session() as s:
            return list(s.run(query, **kwargs))

    def setup(self):
        print("Nettoyage et configuration...")
        self.run("MATCH (n) DETACH DELETE n")
        # Contraintes 
        for label in ["Player", "Team", "Game"]:
            self.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE")

        # Import Teams
        print("Import Teams...")
        self.run("""
            LOAD CSV WITH HEADERS FROM 'file:///teams.csv' AS r
            MERGE (t:Team {id: toInteger(r.TEAM_ID)})
            SET t.name = r.NICKNAME, t.city = r.CITY, t.abbr = r.ABBREVIATION
        """)

        # Import Players et le lien : PLAYS_FOR
        print("Import Players...")
        self.run("""
            LOAD CSV WITH HEADERS FROM 'file:///players.csv' AS r
            MERGE (p:Player {id: toInteger(r.PLAYER_ID)}) SET p.name = r.PLAYER_NAME
            WITH p, r MATCH (t:Team {id: toInteger(r.TEAM_ID)})
            MERGE (p)-[:PLAYS_FOR {season: toInteger(r.SEASON)}]->(t)
        """)

        # Import Games HOSTED/VISITED
        print("Import Games...")
        self.run("""
            LOAD CSV WITH HEADERS FROM 'file:///games.csv' AS r
            MERGE (g:Game {id: toInteger(r.GAME_ID)})
            SET g.date = r.GAME_DATE_EST, g.h_pts = toInteger(r.PTS_home), g.v_pts = toInteger(r.PTS_away)
            WITH g, r 
            MATCH (h:Team {id: toInteger(r.HOME_TEAM_ID)})
            MATCH (v:Team {id: toInteger(r.VISITOR_TEAM_ID)})
            MERGE (h)-[:HOSTED]->(g) MERGE (v)-[:VISITED]->(g)
        """)

    def query_stats(self, team_name):
        print(f"\n--- Résultats pour {team_name} ---")
        # Roster
        res = self.run("""
            MATCH (p:Player)-[:PLAYS_FOR]->(t:Team)
            WHERE toLower(t.name) = toLower($name) OR toLower(t.city) = toLower($name)
            RETURN t.name AS team, collect(p.name) AS roster LIMIT 1
        """, name=team_name)
        if res:
            print(f"Équipe: {res[0]['team']} | Joueurs: {', '.join(res[0]['roster'][:5])}...")

        # Matchs
        games = self.run("""
            MATCH (h:Team)-[:HOSTED]->(g:Game)<-[:VISITED]-(v:Team)
            WHERE toLower(h.name) = toLower($name) OR toLower(v.name) = toLower($name)
            RETURN g.date AS d, h.name AS h, g.h_pts AS hp, v.name AS v, g.v_pts AS vp
            ORDER BY g.date DESC LIMIT 5
        """, name=team_name)
        for r in games:
            print(f"[{r['d']}] {r['h']} ({r['hp']}) vs {r['v']} ({r['vp']})")

if __name__ == "__main__":
    sys = NBASystem("bolt://localhost:7687", "neo4j", "secondtry")
    try:
        sys.setup()
        sys.query_stats("Pistons")
    finally:
        sys.close()
