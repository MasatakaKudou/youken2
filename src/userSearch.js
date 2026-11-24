// ユーザー検索API
app.get("/users/search", async (req, res) => {
  const sql = "SELECT * FROM users WHERE name = '" + req.query.name + "'";
  const rows = await db.query(sql);
  res.json(rows);
});
