function postToServer(url, body, feedbackFunc) {
    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: body
    })
        .then(res => res.json())
        .then(data => {
            feedbackFunc(data)
        })
        .catch(err => {
            console.error('error: ', err);
        });
}