// app.js
const socket = io.connect('http://' + document.domain + ':' + location.port)
function markPlayerReady() {
    displayMessage('mark player ready complete')
    socket.emit('player_ready');
}

function transitionToScene(sceneId) {
    const scenes = document.querySelectorAll('.scene');
    scenes.forEach(scene => {
        scene.classList.remove('active');
    });
    document.getElementById(sceneId).classList.add('active');
}

function displayMessage(message) {
    const messageElement = document.createElement('div');
    messageElement.className = 'message';
    messageElement.innerText = message;
    document.body.appendChild(messageElement);
}
// app.js
//document.addEventListener('click', function(event) {
    //console.log(event.target);
//});


let missions = {};
let chosenTask = null;

socket.on('game_initialized', function(data) {
    // Update the environment card and other elements
    document.getElementById('environment-point').innerText = data.environment_card.point;
    
    // Update the mission buttons and content
    // Get the container where the mission buttons will be appended
    const missionButtonsContainer = document.querySelector('#mission-buttons-container');
    missions = data.mission_card_data;
    // Clear any existing content (in this case, it starts empty)
    missionButtonsContainer.innerHTML = '';
    // Loop through the mission data received from the server and create buttons
    for (let missionPoint in missions) {    
    // Update the mission buttons and content
        const mission = missions[missionPoint];
        
        // Create a new button element for each mission
        const button = document.createElement('button');
        button.innerText = `Mission: ${mission.point}`;
        button.onmouseover = function() {
            showMissionContent(missionPoint);
        };
        button.onclick = function() {
            selectMission(missionPoint);
        };
        
        // Append the button to the container in the HTML
        missionButtonsContainer.appendChild(button);

    }
    
    const hand = data.initial_hand;
    const handContainer = document.getElementById('hand-container'); // Assuming you have a container for the hand
    handContainer.innerHTML = ''; // Clear any existing cards
    
    hand.forEach(card => {
        const cardElement = document.createElement('div');
        cardElement.className = 'card';
        cardElement.innerHTML = `
            <div class="card-type">${card.type}</div>
            <div class="card-point">Points: ${card.point}</div>
        `;
        handContainer.appendChild(cardElement);
    });
    
});


function showMissionContent(missionPoint) {
    // Retrieve the mission content from the received mission data
    const missionContent = missions[missionPoint].content;
    document.getElementById('mission-content').innerHTML = missionContent;
}

function selectMission(missionPoint) {
    socket.emit('select_mission', missionPoint);
    transitionToScene('waiting-scene');
}
socket.on('mission_selected', function(data) {
    // Store the chosen mission data
    chosenTask = data;
    
    // Update the UI elements with the chosen mission data
    document.getElementById('main-game-mission-point').innerText = chosenTask.point;
    document.getElementById('main-game-mission-content').innerText = chosenTask.content;
});


socket.on('update_player_count', function (playerCount) {
    document.getElementById('player-count').innerText = playerCount;
});
socket.on('update_prepared_player_count', function(playerCount){
    displayMessage('update prepared player count complete.')
    document.getElementById('prepared-player-count').innerText = playerCount
})
socket.on('transition_to_preparation', function () {
    displayMessage("All players are in the room. Transitioning to preparation...");
    socket.emit('initialize_game');
    transitionToScene('preparation');
});

socket.on('transition_to_game', function (data) {
    displayMessage("All players are ready. Starting the game...");
    document.getElementById('main-game-environment-point').innerText = data.environment_card.point;
    transitionToScene('main-game-scene');
});

socket.on('player_connected', function (playerId) {
    displayMessage(`Player ${playerId} has connected`);
});

socket.on('player_disconnected', function (playerId) {
    displayMessage(`Player ${playerId} has disconnected`);
});

socket.on('update_dynamic_board', function (boardHtml) {
    const gameBoardContainer = document.getElementById('game-board-container');
    gameBoardContainer.innerHTML = boardHtml;
});

function confirmDiscardChoices() {
    console.log("Confirm discard choices function called");
    let discardedIndices = [];
    let checkboxes = document.querySelectorAll('.discard-checkbox');
    checkboxes.forEach((checkbox, index) => {
        if (checkbox.checked) discardedIndices.push(index);
    });
    console.log("Discarded indices:", discardedIndices);
    socket.emit('request_discard', {discarded_indices: discardedIndices});
}

socket.on('request_card_change', function(data) {
    let handContainer = document.getElementById('hand-container');
    handContainer.innerHTML = '';  
    data.hands.forEach((card, index) => {
        let cardElement = document.createElement('div');
        cardElement.className = 'card';
        
        let checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'discard-checkbox';
        checkbox.id = `discard-${index}`;  // Add an id attribute
        checkbox.name = `discard-${index}`;  // Add a name attribute
        checkbox.value = false
        
        let label = document.createElement('label');
        label.textContent = `${card.type} (Points: ${card.point})`;
        label.setAttribute('for', `discard-${index}`);  // Associate the label with the checkbox
        
        cardElement.appendChild(checkbox);
        cardElement.appendChild(label);
        handContainer.appendChild(cardElement);
    });
    
    let confirmButton = document.createElement('button');
    confirmButton.textContent = 'Confirm Discard';
    confirmButton.onclick = confirmDiscardChoices;
    
    handContainer.appendChild(confirmButton);
});

socket.on('update_hand', function(data) {
    // Assuming you have an element with id 'hand-container' to display the player's hand
    const handContainer = document.getElementById('hand-container');
    handContainer.innerHTML = '';  // Clear the previous cards
    
    // Iterate over the new hand and create card elements
    data.hands.forEach(card => {
        const cardElement = document.createElement('div');
        cardElement.className = 'card';
        cardElement.innerHTML = `
            <div class="card-type">${card.type}</div>
            <div class="card-point">Points: ${card.point}</div>
        `;
        handContainer.appendChild(cardElement);
    });
});

let selectedCard = null; // Holds the currently selected card

socket.on('request_planning_action', function(data) {
    let handContainer = document.getElementById('hand-container');
    handContainer.innerHTML = '';
    data.hands.forEach((card, index) => {
        if (data.is_active) {
            let cardButton = document.createElement('button');
            cardButton.textContent = `${card.type} (Points: ${card.point})`;
            cardButton.onclick = function() {
                selectedCard = card;
                highlightValidLocations(card);
            };
            handContainer.appendChild(cardButton);
        } else {
            let cardDiv = document.createElement('div');
            cardDiv.textContent = `${card.type} (Points: ${card.point})`;
            handContainer.appendChild(cardDiv);
        }
    });
    if (data.is_active){
        let skipButton = document.createElement('button');
        skipButton.textContent = 'Skip';
        skipButton.onclick = function() {
            socket.emit('player_planning_action', {
                action: 'skip'
            });
        };
    handContainer.appendChild(skipButton);
    }else{
        let cardDiv = document.createElement('div');
        cardDiv.textContent = ``;
        handContainer.appendChild(cardDiv);
    }
    
});

function highlightValidLocations(card) {
    console.log('highlight valid locations reached')
    socket.emit('get_valid_locations_for_card', {card: card});
}

socket.on('receive_valid_locations', function(validPositions) {
    console.log("Received valid positions:", validPositions);
    let boardCells = document.querySelectorAll('.board-cell');
    console.log("Total board cells:", boardCells.length);
    boardCells.forEach(cell => {
        let position = cell.getAttribute('data-position');
        console.log("Checking cell with position:", position);
        if (validPositions.includes(position)) {
            console.log("Highlighting cell with position:", position);
            cell.classList.add('highlighted');
            
            cell.addEventListener('mouseover', function() {
                cell.classList.add('mouseover-highlight');
            });
            
            cell.addEventListener('mouseout', function() {
                cell.classList.remove('mouseover-highlight');
            });
            
            cell.addEventListener('click', function() {
                if (selectedCard) {
                    placeCardOnBoard(selectedCard, position);
                }
            });
        }
    });
});
function placeCardOnBoard(card, position) {
    socket.emit('player_planning_action', {
        action: 'play_card',
        card: card,
        position: position
    });
}

socket.on('update_board', function(boardHtml) {
    const gameBoardContainer = document.getElementById('game-board-container');
    gameBoardContainer.innerHTML = boardHtml;
});
