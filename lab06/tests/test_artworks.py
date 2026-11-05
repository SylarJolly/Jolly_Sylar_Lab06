import pytest

#------------------------------------HAPPY PATHS-------------------------------------------

# 1. TEST FOR EMPTY ARTWORKS
def test_list_artworks_empty(client):

    # Act
    response = client.get("/artworks/")

    # Assert
    assert response.status_code == 200
    assert response.json() == []


# 2. TEST FOR GETTING A SEEDED ARTWORK
def test_get_seeded_artwork(client, seeded_db):
    # Arrange: seeded_db has already loaded the 11 artworks (the Mona Lisa is first)
    expected = {"id": 1, **seeded_db[0]}

    # Act
    response = client.get("/artworks/1")

    # Assert
    assert response.status_code == 200
    assert response.json() == expected


# 3. TEST FOR CREATING AN ARTWORK
def test_create_artwork(client, sample_artwork):

    # Act
    response = client.post("/artworks/", json=sample_artwork)

    # Assert
    assert response.status_code == 201

    artwork = response.json()

    assert isinstance(artwork["id"], int)
    assert artwork["id"] > 0
    assert {key: value for key, value in artwork.items() if key != "id"} == sample_artwork


# 4. TEST FOR CHECKING IF A CREATED ARTWORK WAS SAVED
def test_create_artwork_is_saved(client, created_artwork):

    # Act
    artwork_id = created_artwork["id"]
    response = client.get(f"/artworks/{artwork_id}")

    # Assert
    assert response.status_code == 200
    assert response.json() == created_artwork


# 5. TEST FOR UPDATING AN ARTWORK
def test_update_artwork(client, created_artwork, updated_artwork):

    # Arrange
    artwork_id = created_artwork["id"]
    expected = {"id": artwork_id, **updated_artwork}

    # Act
    response = client.put(f"/artworks/{artwork_id}", json=updated_artwork)

    # Assert
    assert response.status_code == 200
    assert response.json() == expected

    get_response = client.get(f"/artworks/{artwork_id}")

    assert get_response.status_code == 200
    assert get_response.json() == expected

# 6. TEST FOR DELETING AN ARTWORK
def test_delete_artwork(client, created_artwork):

    # Arrange
    artwork_id = created_artwork["id"]

    # Act
    response = client.delete(f"/artworks/{artwork_id}")

    # Assert
    assert response.status_code == 204
    assert response.content == b""

    get_response = client.get(f"/artworks/{artwork_id}")

    assert get_response.status_code == 404

#------------------------------------UNHAPPY PATHS-------------------------------------------


# 7. TEST FOR ARTWORK NOT FOUND
@pytest.mark.parametrize(
    "method, use_body",
    [
        ("get", False),
        ("put", True),
        ("delete", False),
    ],
    ids=["get", "put", "delete"],
)
def test_artwork_not_found(client, sample_artwork, method, use_body):
    kwargs = {"json": sample_artwork} if use_body else {}
    response = client.request(method, "/artworks/9999", **kwargs)
    assert response.status_code == 404
    assert response.json() == {"detail": "Artwork not found"}


# 8. TEST FOR NON-INTEGER ARTWORK ID
def test_non_integer_id(client):

    # Act
    response = client.get("/artworks/mona-lisa")

    # Assert
    assert response.status_code == 422


# 9. TEST FOR CREATING A DUPLICATE ARTWORK
def test_create_duplicate(client, created_artwork, sample_artwork):

    # Act
    response = client.post("/artworks/", json=sample_artwork)

    # Assert
    assert response.status_code == 409
    assert response.json()["detail"] == "An artwork with that title and artist already exists"

# 10. TEST FOR DUPLICATE ARTWORK IGNORING CASE
def test_create_duplicate_ignores_case(client, created_artwork, sample_artwork):

    # Arrange
    duplicate_artwork = sample_artwork.copy()
    duplicate_artwork["title"] = duplicate_artwork["title"].upper()
    duplicate_artwork["artist"] = duplicate_artwork["artist"].lower()

    # Act
    response = client.post("/artworks/", json=duplicate_artwork)

    # Assert
    assert response.status_code == 409


# 11. TEST FOR UPDATING AN ARTWORK INTO A DUPLICATE
def test_update_into_duplicate(client, seeded_db):

    # Arrange
    duplicate_artwork = seeded_db[0].copy()

    # Act
    response = client.put("/artworks/2", json=duplicate_artwork)

    # Assert
    assert response.status_code == 409

    # Check that artwork 2 was not changed
    get_response = client.get("/artworks/2")

    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Lady with an Ermine"
    assert get_response.json()["artist"] == "Leonardo da Vinci"


# 12. TEST FOR UPDATING AN ARTWORK WITHOUT CREATING A DUPLICATE
def test_update_same_title_and_artist_is_allowed(client, created_artwork):

    # Arrange
    updated_artwork = created_artwork.copy()
    updated_artwork["museum"] = "The Metropolitan Museum of Art"

    # Act
    artwork_id = created_artwork["id"]
    response = client.put(f"/artworks/{artwork_id}", json=updated_artwork)

    # Assert
    assert response.status_code == 200
    assert response.json()["title"] == created_artwork["title"]
    assert response.json()["artist"] == created_artwork["artist"]
    assert response.json()["museum"] == "The Metropolitan Museum of Art"


# 13. TEST FOR CREATING AN ARTWORK WITH A MISSING FIELD
@pytest.mark.parametrize(
    "missing_field",
    ["title", "artist", "year", "medium", "museum", "image_url"],
    ids=["title", "artist", "year", "medium", "museum", "image-url"]
)
def test_create_missing_field(client, sample_artwork, missing_field):

    # Arrange
    artwork = sample_artwork.copy()
    artwork.pop(missing_field)

    # Act
    response = client.post("/artworks/", json=artwork)

    # Assert
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", missing_field]


#14. TEST FOR CREATING AN ARTWORK WITH AN INVALID VALUE
@pytest.mark.parametrize(
    "field, invalid_value",
    [
        ("year", 3000),
        ("year", "nineteen-oh-seven"),
        ("title", ""),
    ],
    ids=["future-year", "year-not-int", "empty-title"]
)
def test_create_invalid_value(client, sample_artwork, field, invalid_value):

    # Arrange
    artwork = sample_artwork.copy()
    artwork[field] = invalid_value

    # Act
    response = client.post("/artworks/", json=artwork)

    # Assert
    assert response.status_code == 422


# 15. TEST FOR PAGINATION COUNTS
@pytest.mark.parametrize(
    "skip, limit, expected_count",
    [
        (0, 3, 3),      # First 3 artworks
        (3, 3, 3),      # Skip 3, return next 3
        (0, 0, 0),      # Limit of 0
        (20, 3, 0),     # Skip past the end of the data
    ],
    ids=["first-three", "next-three", "zero-limit", "skip-past-end"]
)
def test_pagination_counts(client, seeded_db, skip, limit, expected_count):

    # Act
    response = client.get(
        "/artworks/",
        params={"skip": skip, "limit": limit}
    )

    # Assert
    assert response.status_code == 200
    assert len(response.json()) == expected_count


# 16. TEST FOR INVALID PAGINATION VALUES
@pytest.mark.parametrize(
    "params",
    [
        {"skip": -1},   # Skip cannot be negative
        {"limit": 101},
    ],
    ids=["negative-skip", "zero-limit"]
)
def test_pagination_invalid(client, seeded_db, params):

    # Act
    response = client.get("/artworks/", params=params)

    # Assert
    assert response.status_code == 422


# 17. TEST FOR FILTERING ARTWORKS BY ARTIST
@pytest.mark.parametrize(
    "artist, expected_titles",
    [
        ("Leonardo da Vinci", ["Mona Lisa", "Lady with an Ermine"]),
        ("da vinci", ["Mona Lisa", "Lady with an Ermine"]),
        ("Not an Artist", []),
    ],
    ids=["full-name", "partial-lowercase", "no-results"]
)
def test_filter_by_artist(client, seeded_db, artist, expected_titles):

    # Act
    response = client.get("/artworks/", params={"artist": artist})

    # Assert
    assert response.status_code == 200

    actual_titles = [artwork["title"] for artwork in response.json()]
    assert actual_titles == expected_titles